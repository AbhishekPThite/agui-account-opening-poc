import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

export interface AgUiEvent {
  type: string;
  [key: string]: unknown;
}

export interface RunAgentInput {
  threadId: string;
  runId: string;
  messages: Array<{
    id: string;
    role: 'user';
    content: string;
  }>;
  resume?: Array<{
    interruptId: string;
    status: 'resolved';
    payload: unknown;
  }>;
}

@Injectable({ providedIn: 'root' })
export class AguiClientService {
  run(input: RunAgentInput): Observable<AgUiEvent> {
    return new Observable<AgUiEvent>(subscriber => {
      const controller = new AbortController();

      const processFrame = (frame: string): void => {
        const data = frame
          .split(/\r\n|\n|\r/)
          .filter(line => line.startsWith('data:'))
          .map(line => line.slice(5).replace(/^ /, ''))
          .join('\n');

        if (!data || data === '[DONE]') return;

        try {
          const event = JSON.parse(data) as AgUiEvent;
          console.log('[AG-UI EVENT]', event);
          subscriber.next(event);
        } catch (error) {
          console.error('[AG-UI PARSE ERROR]', data, error);
        }
      };

      const execute = async (): Promise<void> => {
        try {
          const response = await fetch('/agent', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Accept': 'text/event-stream',
            },
            body: JSON.stringify(input),
            signal: controller.signal,
          });

          console.log('[AG-UI HTTP STATUS]', response.status);
          console.log(
            '[AG-UI CONTENT TYPE]',
            response.headers.get('content-type')
          );

          if (!response.ok || !response.body) {
            throw new Error(
              `AG-UI request failed: HTTP ${response.status} ${await response.text()}`
            );
          }

          const reader = response.body.getReader();
          const decoder = new TextDecoder();
          let buffer = '';

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });

            // SSE events are separated by a blank line.
            const frames = buffer.split(/\r\n\r\n|\n\n|\r\r/);
            buffer = frames.pop() ?? '';

            for (const frame of frames) {
              processFrame(frame);
            }
          }

          // Flush the decoder and process a final unterminated frame, if present.
          buffer += decoder.decode();
          if (buffer.trim()) {
            processFrame(buffer);
          }

          subscriber.complete();
        } catch (error: any) {
          if (error?.name !== 'AbortError') {
            console.error('[AG-UI STREAM ERROR]', error);
            subscriber.error(error);
          }
        }
      };

      void execute();
      return () => controller.abort();
    });
  }
}
