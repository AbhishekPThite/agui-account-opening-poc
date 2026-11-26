import { CommonModule } from '@angular/common';
import { Component, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { AgUiEvent, AguiClientService } from './agui-client.service';
@Component({selector:'app-account-opening-agent',standalone:true,imports:[CommonModule,FormsModule],templateUrl:'./account-opening-agent.component.html'})
export class AccountOpeningAgentComponent {
  prompt=signal('Open a joint brokerage account for client C12345 with USD as base currency.');
  ownerName=signal(''); taxResidency=signal(''); readonly threadId=crypto.randomUUID();
  events=signal<AgUiEvent[]>([]); assistantText=signal<string[]>([]); uiState=signal<Record<string,unknown>|null>(null); busy=signal(false); error=signal('');
  constructor(private readonly agui:AguiClientService){}
  start():void{this.events.set([]);this.assistantText.set([]);this.uiState.set(null);this.send(this.prompt());}
  submitJointOwner():void{this.send(`Joint owner name: ${this.ownerName()}, tax residency: ${this.taxResidency()}`);}
  private send(text:string):void{if(this.busy())return;this.busy.set(true);this.error.set('');this.agui.run({threadId:this.threadId,runId:crypto.randomUUID(),messages:[{id:crypto.randomUUID(),role:'user',content:text}]}).subscribe({next:e=>this.handleEvent(e),error:(e:Error)=>{this.error.set(e.message);this.busy.set(false);},complete:()=>this.busy.set(false)});}
  private handleEvent(event:AgUiEvent):void{
    this.events.update(items=>[...items,event]);
    if(event.type==='STATE_SNAPSHOT'){const snap=event['snapshot'] as Record<string,unknown>|undefined;if(snap?.['ui'])this.uiState.set(snap['ui'] as Record<string,unknown>);}
    if(event.type==='TEXT_MESSAGE_START')this.assistantText.update(items=>[...items,'']);
    if(event.type==='TEXT_MESSAGE_CONTENT'){const delta=String(event['delta']??'');this.assistantText.update(items=>{const copy=[...items];if(!copy.length)copy.push(delta);else copy[copy.length-1]=(copy[copy.length-1]??'')+delta;return copy;});}
    if(event.type==='RUN_ERROR')this.error.set(String(event['message']??'Agent run failed'));
  }
}