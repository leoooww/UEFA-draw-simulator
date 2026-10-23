import { Injectable } from '@angular/core';
import { webSocket, WebSocketSubject } from 'rxjs/webSocket';
import { Observable } from 'rxjs';

@Injectable({
  providedIn: 'root'
})
export class TerminalService {
  private socket$: WebSocketSubject<any>;

  constructor() {
    this.socket$ = webSocket('ws://127.0.0.1:8000/ws');
  }

  getMessages(): Observable<any> {
    return this.socket$.asObservable();
  }

  startDraw() {
    console.log('Starting draw...');
    this.socket$.next({ action: 'start_draw' });
  }

  continueDraw() {
    console.log('Continuing draw...');
    this.socket$.next({ action: 'continue_draw' });
  }
}