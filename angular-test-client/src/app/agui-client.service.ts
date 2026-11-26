import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';
export interface AgUiEvent { type: string; [key: string]: unknown; }
export interface RunAgentInput { threadId: string; runId: string; messages: Array<{id:string;role:'user';content:string}>; }
@Injectable({providedIn:'root'})
export class AguiClientService {
  run(input: RunAgentInput): Observable<AgUiEvent> {
    return new Observable<AgUiEvent>(subscriber => {
      const controller = new AbortController();
      fetch('/agent',{method:'POST',headers:{'Content-Type':'application/json','Accept':'text/event-stream'},body:JSON.stringify(input),signal:controller.signal})
        .then(async response => {
          if (!response.ok || !response.body) throw new Error(`AG-UI request failed: HTTP ${response.status} ${await response.text()}`);
          const reader=response.body.getReader(); const decoder=new TextDecoder(); let buffer='';
          while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const frames=buffer.split(/\\r?\\n\\r?\\n/);buffer=frames.pop()??'';
            for(const frame of frames){const data=frame.split(/\\r?\\n/).filter(line=>line.startsWith('data:')).map(line=>line.slice(5).trim()).join('\\n');if(!data||data==='[DONE]')continue;try{subscriber.next(JSON.parse(data) as AgUiEvent);}catch{/* Ignore non-JSON SSE frames in this smoke-test client. */}}
          } subscriber.complete();
        }).catch(error=>{if(error?.name!=='AbortError')subscriber.error(error);});
      return ()=>controller.abort();
    });
  }
}