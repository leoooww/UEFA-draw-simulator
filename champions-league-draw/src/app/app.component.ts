import { Component } from '@angular/core';
import { NgIf } from '@angular/common';
import { SequentialDraw } from './sequential-draw.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [NgIf, SequentialDraw],
  template: `
    <div class="container">  
      <sequential-draw></sequential-draw>
    </div>
  `,
  styleUrls: ['./app.component.scss']
})
export class AppComponent {
  title = 'champions-league-draw';
}