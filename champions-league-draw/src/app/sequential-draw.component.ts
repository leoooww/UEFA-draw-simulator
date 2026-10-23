import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TerminalService } from './terminal.service';
import { FormsModule } from '@angular/forms';

interface Match {
    selectedTeam: string;
    selectedPot: number;
    homeTeam: string;
    awayTeam: string;
}
@Component({
  selector: 'sequential-draw',
  standalone: true,
  imports: [CommonModule, FormsModule],
  styles: [`
    :host {
      display: block;
      min-height: 100vh;
      background:linear-gradient(45deg, #080e3a,rgb(33, 0, 90));
      color: white;
    }

    .header {
      position: fixed;
      top: 0;
      left: 0;
      right: 0;
      backdrop-filter: blur(10px);
      background: rgba(8, 14, 58, 0.34);
      padding: 1rem 2rem;
      border-bottom: 1px solid rgba(255, 255, 255, 0.1);
      z-index: 100;
      text-align: left;
    }

    .header h1 {
      font-size: 1rem;
      font-weight: 1000;
      margin: 0;
      color: rgba(255, 255, 255, 0.95);
      text-align: left;  /* Ajout de cette ligne */
    }

    .container {
      padding-top: calc(4rem + 16px); 
      width: 100%;
      overflow-x: auto;
      min-height: 100vh;
      backdrop-filter: blur(8px);
      background: rgba(8, 14, 58, 0.4);
    }

    .tables-row {
      display: flex;
      gap: 2%;
      margin-bottom: 2rem;
      width: 100%;
      justify-content: space-between;
    }

    .table-container {
      flex: 1;
      width: 49%;
      margin-bottom: 1.5rem;
      backdrop-filter: blur(12px);
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 12px;
      padding: 1.2rem;
      transition: transform 0.2s ease;
    }

    table {
      width: 100%;
      table-layout: fixed;
    }

    th, td {
      border: 1px solid rgba(255, 255, 255, 0.1);
      padding: 0.4rem;
      text-align: center;
      width: auto !important;
      height: 32px;
      overflow: hidden;
      white-space: nowrap;
      text-overflow: ellipsis;
      color: rgba(255, 255, 255, 0.87);
      box-sizing: border-box;
      font-size: 0.9rem;
    }

    .team-column {
      width: 15% !important;
    }

    .pot-header {
      border-bottom: none;
      background: rgba(255, 255, 255, 0.08);
      color: rgba(255, 255, 255, 0.87);
      width: 21.25% !important;
    }

    .pot-title {
      font-size: 1.2rem;
      font-weight: 500;
      margin: 0 0 1.2rem;
      color: rgba(255, 255, 255, 0.95);
      letter-spacing: 0.025em;
    }

    .subheader {
      border-top: none;
      font-size: 0.85rem;
      background:rgba(12, 21, 89, 0.45);
    }

    .draw-button {
      background: linear-gradient(45deg, #2563eb, #7c3aed);
      color: white;
      border: none;
      padding: 1rem 2rem;
      font-size: 1.1rem;
      cursor: pointer;
      border-radius: 8px;
      width: auto;
      max-width: 1200px;
      margin: 2rem auto;
      display: flex;
      justify-content: center;
      align-items: center;
      gap: 0.5rem;
      transition: all 0.3s ease;
      font-weight: 500;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    }

    .draw-button:hover:not([disabled]) {
      transform: translateY(-2px);
      box-shadow: 0 6px 8px -1px rgba(0, 0, 0, 0.15), 0 3px 6px -1px rgba(0, 0, 0, 0.1);
      background: linear-gradient(45deg, #1d4ed8, #6d28d9);
    }

    .draw-button[disabled] {
      opacity: 0.7;
      cursor: not-allowed;
      transform: none;
    }

    .csv-button {
      background: linear-gradient(45deg, #22c55e, #059669);
      padding: 0.75rem 1.5rem;
      font-size: 0.9rem;
      width: auto;
      margin-left: 1rem;
    }

    .csv-button:hover:not([disabled]) {
      background: linear-gradient(45deg, #16a34a, #047857);
    }

    .pot-title {
      font-size: 1.25rem;
      font-weight: 500;
      margin: 0 0 1.5rem;
      color: rgba(255, 255, 255, 0.95);
      letter-spacing: 0.025em;
    }

    @keyframes highlight {
      0% { background-color: transparent; }
      50% { background-color: rgba(34, 197, 94, 0.2); }
      100% { background-color: transparent; }
    }
    
    .highlight {
      animation: highlight 1s ease;
    }

    .loading-spinner {
      display: inline-block;
      width: 15px;
      height: 15px;
      border: 2px solid rgba(255, 255, 255, 0.3);
      border-radius: 50%;
      border-top-color: white;
      animation: spin 1s linear infinite;
    }

    @keyframes spin {
      0% { transform: rotate(0deg); }
      100% { transform: rotate(360deg); }
    }

    .controls {
      display: flex;
      align-items: center;
      gap: 1rem;
      margin: 2rem auto;
      padding: 0 2rem;
      max-width: 1200px;
    }

    .auto-mode {
      display: flex;
      align-items: center;
      gap: 0.5rem;
      padding: 0.5rem 1rem;
      background: rgba(255, 255, 255, 0.1);
      border-radius: 8px;
    }

    .auto-checkbox {
      width: 1.2rem;
      height: 1.2rem;
      cursor: pointer;
    }

    .auto-label {
      color: white;
      font-size: 1rem;
      cursor: pointer;
    }
  `],
  template: `
    <div class="header">
      <h1>⚽️ Simulation of the Champions League league phase</h1>
    </div>

    <div class="container">
      <button 
        (click)="handleDraw()"
        class="draw-button"
        [disabled]="waitingForInput || updateInProgress"
      >
        <span>{{isDrawing ? 'Continue the draw' : 'Start the draw'}}</span>
        <div class="loading-spinner" *ngIf="waitingForInput || updateInProgress"></div> 
      </button>
      <button 
        (click)="exportToCSV()"
        class="draw-button csv-button"
        [disabled]="!Object.keys(matches).length"
      >
        Export to CSV
      </button>
      <div class="auto-mode">
        <input 
          type="checkbox" 
          id="autoMode" 
          [(ngModel)]="autoMode"
          class="auto-checkbox"
        >
        <label for="autoMode" class="auto-label">Auto mode</label>
      </div>

      <div class="tables-row">
        <!-- Première ligne : Pots 1 et 2 -->
        <div *ngFor="let pot of pots.slice(0, 2); let potIndex = index" class="table-container">
          <h3 class="pot-title">Pot {{potIndex + 1}}</h3>
          <table>
            <thead>
              <tr>
                <th class="team-column"></th>
                <th class="pot-header" colspan="2">Pot 1</th>
                <th class="pot-header" colspan="2">Pot 2</th>
                <th class="pot-header" colspan="2">Pot 3</th>
                <th class="pot-header" colspan="2">Pot 4</th>
              </tr>
              <tr>
                <th class="team-column subheader"></th>
                <th class="subheader">Home</th>
                <th class="subheader">Away</th>
                <th class="subheader">Home</th>
                <th class="subheader">Away</th>
                <th class="subheader">Home</th>
                <th class="subheader">Away</th>
                <th class="subheader">Home</th>
                <th class="subheader">Away</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let team of pot; let teamIndex = index">
                <td class="team-column">{{team}}</td>
                <td [class.highlight]="isRecentMatch(potIndex, teamIndex, 0, true)">
                {{getOpponent(potIndex, teamIndex, 0, true)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex, teamIndex, 0, false)">
                {{getOpponent(potIndex, teamIndex, 0, false)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex, teamIndex, 1, true)">
                {{getOpponent(potIndex, teamIndex, 1, true)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex, teamIndex, 1, false)">
                {{getOpponent(potIndex, teamIndex, 1, false)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex, teamIndex, 2, true)">
                {{getOpponent(potIndex, teamIndex, 2, true)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex, teamIndex, 2, false)">
                {{getOpponent(potIndex, teamIndex, 2, false)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex, teamIndex, 3, true)">
                {{getOpponent(potIndex, teamIndex, 3, true)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex, teamIndex, 3, false)">
                {{getOpponent(potIndex, teamIndex, 3, false)}}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>

      <div class="tables-row">
        <!-- Deuxième ligne : Pots 3 et 4 -->
        <div *ngFor="let pot of pots.slice(2, 4); let potIndex = index" class="table-container">
          <h3 class="pot-title">Pot {{potIndex + 3}}</h3>
          <table>
            <thead>
              <tr>
                <th class="team-column"></th>
                <th class="pot-header" colspan="2">Pot 1</th>
                <th class="pot-header" colspan="2">Pot 2</th>
                <th class="pot-header" colspan="2">Pot 3</th>
                <th class="pot-header" colspan="2">Pot 4</th>
              </tr>
              <tr>
                <th class="team-column subheader"></th>
                <th class="subheader">Home</th>
                <th class="subheader">Away</th>
                <th class="subheader">Home</th>
                <th class="subheader">Away</th>
                <th class="subheader">Home</th>
                <th class="subheader">Away</th>
                <th class="subheader">Home</th>
                <th class="subheader">Away</th>
              </tr>
            </thead>
            <tbody>
              <tr *ngFor="let team of pot; let teamIndex = index">
                <td class="team-column">{{team}}</td>
                <td [class.highlight]="isRecentMatch(potIndex+2 , teamIndex, 0, true)">
                {{getOpponent(potIndex+2, teamIndex, 0, true)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex+2, teamIndex, 0, false)">
                {{getOpponent(potIndex+2, teamIndex, 0, false)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex+2, teamIndex, 1, true)">
                {{getOpponent(potIndex+2, teamIndex, 1, true)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex+2, teamIndex, 1, false)">
                {{getOpponent(potIndex+2, teamIndex, 1, false)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex+2, teamIndex, 2, true)">
                {{getOpponent(potIndex+2, teamIndex, 2, true)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex+2, teamIndex, 2, false)">
                {{getOpponent(potIndex+2, teamIndex, 2, false)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex+2, teamIndex, 3, true)">
                {{getOpponent(potIndex+2, teamIndex, 3, true)}}
                </td>
                <td [class.highlight]="isRecentMatch(potIndex+2, teamIndex, 3, false)">
                {{getOpponent(potIndex+2, teamIndex, 3, false)}}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `
})


export class SequentialDraw implements OnInit, OnDestroy{
  isDrawing = false;
  waitingForInput = false;
  matches: { [key: string]: Match } = {};
  recentMatch: Match | null = null;
  highlightTimeout: any = null;
  updateInProgress = false;
  autoMode = false;
  private autoModeTimeout: any = null;
  Object = Object;

  pots = [
    ["Real", "ManCity", "Bayern", "PSG", "Liverpool", "Inter", "Dortmund", "Leipzig", "Barcelona"],
    ["Leverkusen", "Atlético", "Atalanta", "Juventus", "Benfica", "Arsenal", "Brugge", "Shakhtar", "Milan"],
    ["Feyenoord", "Sporting", "Eindhoven", "Dinamo", "Salzburg", "Lille", "Crvena", "YB", "Celtic"],
    ["Bratislava", "Monaco", "Sparta", "Aston Villa", "Bologna", "Girona", "Stuttgart", "Sturm Graz", "Brest"]
  ];

  constructor(private terminalService: TerminalService) {}

  handleDraw() {
    if (this.updateInProgress) return; 
    
    if (!this.isDrawing) {
      this.isDrawing = true;
      this.matches = {};
      this.waitingForInput = true;
      this.terminalService.startDraw();
    } else {
      console.log('Envoi de la commande continue');
      this.waitingForInput = true;
      this.terminalService.continueDraw();
    }
  }

getOpponent(potIndex: number, teamIndex: number, oppPotIndex: number, isHome: boolean): string {
    const currentTeam = this.pots[potIndex][teamIndex];
    
    for (const [key, match] of Object.entries(this.matches)) {
        // Ne regarder que la ligne de l'équipe sélectionnée
        if (match.selectedTeam === currentTeam) {
            // Et si c'est dans la bonne colonne (le bon pot)
            if (match.selectedPot === oppPotIndex) {
                return isHome ? match.homeTeam : match.awayTeam;
            }
        }
    }
    return '';
}

exportToCSV(): void {
  if (!Object.keys(this.matches).length) {
    console.warn('Aucun match disponible pour l\'exportation.');
    return;
  }

  // Construction des données CSV
  const headers = ['Équipe Sélectionnée', 'Pot', 'Domicile', 'Extérieur'];
  const rows = Object.values(this.matches).map(match => [
    match.selectedTeam,
    `Pot ${match.selectedPot + 1}`,
    match.homeTeam,
    match.awayTeam,
  ]);

  const csvContent = [
    headers.join(','), // En-tête CSV
    ...rows.map(row => row.map(cell => `"${cell}"`).join(',')), // Lignes
  ].join('\n');

  // Création et téléchargement du fichier CSV
  const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
  const url = window.URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.href = url;
  a.download = 'matches.csv';
  a.click();

  window.URL.revokeObjectURL(url);
}

ngOnInit() {
  this.terminalService.getMessages().subscribe(
    async (message) => {
      console.log('Message reçu:', message);
      if (message.type === 'terminal_output') {
        // Indication fin du tirage
        if (message.data.includes("Résultats du tirage au sort enregistrés dans le fichier 'result_sequential_uefa_draw.txt'")) {
          // Réinitialisation de tous les états
          this.isDrawing = false;
          this.waitingForInput = false;
          this.updateInProgress = false;
          if (this.autoModeTimeout) {
            clearTimeout(this.autoModeTimeout);
          }
        }
        else if (message.data.includes('Match sélectionné')) {
          this.updateInProgress = true;
          const match = this.parseMatchData(message.data);
          if (match) {
            await this.updateMatches(match);
          }
          await new Promise(resolve => setTimeout(resolve, 10));
          this.updateInProgress = false;
          this.waitingForInput = false;
          
          if (this.autoMode) {
            this.autoModeTimeout = setTimeout(() => {
              if (this.isDrawing && !this.updateInProgress) {
                this.handleDraw();
              }
            }, 10);
          }
        }
      } else if (message.type === 'wait_for_input') {
        if (!this.updateInProgress) {
          this.waitingForInput = false;
          
          if (this.autoMode) {
            this.autoModeTimeout = setTimeout(() => {
              if (this.isDrawing && !this.updateInProgress) {
                this.handleDraw();
              }
            }, 10);
          }
        }
      }
    }
  );
}

private parseMatchData(data: string): Match | null {
    console.log("Data à parser:", data);

    const lines = data.split('\n');
    let selectedTeam = '';
    let selectedPot = -1;

    // Chercher l'équipe sélectionnée et le pot
    for (const line of lines) {
        if (line.includes('Equipe sélectionnée:')) {
            selectedTeam = line.split(':')[1].trim();
            console.log("Équipe trouvée:", selectedTeam);
        }
        if (line.includes('Pot sélectionné:')) {
            selectedPot = parseInt(line.split(':')[1].trim()) - 1;
            console.log("Pot trouvé:", selectedPot + 1);
        }
    }
    const matchRegex = /Match sélectionné dans le pot (\d+) : ([A-Za-zÀ-ÖØ-öø-ÿ\s]+) vs ([A-Za-zÀ-ÖØ-öø-ÿ\s]+)/;
    const matchResult = data.match(matchRegex);
    
    console.log("Match trouvé:", matchResult);

    if (selectedTeam && selectedPot >= 0 && matchResult) {
        const match: Match = {
            selectedTeam: selectedTeam,
            selectedPot: selectedPot,
            homeTeam: matchResult[2].trim(),
            awayTeam: matchResult[3].trim()
        };
        console.log("Match parsé:", match);
        return match;
    }

    console.log("Échec du parsing");
    return null;
}


private updateMatches(match: Match) {
    const key = `${match.selectedTeam}-${match.selectedPot}`;
    this.matches[key] = match;
    
    this.recentMatch = match;
    
    if (this.highlightTimeout) {
        clearTimeout(this.highlightTimeout);
    }
    this.highlightTimeout = setTimeout(() => {
        this.recentMatch = null;
    }, 1000);

    console.log('Matches mis à jour:', this.matches);
}

isRecentMatch(potIndex: number, teamIndex: number, oppPotIndex: number, isHome: boolean): boolean {
    if (!this.recentMatch) return false;
    
    const currentTeam = this.pots[potIndex][teamIndex];
    
    return this.recentMatch.selectedTeam === currentTeam && 
           this.recentMatch.selectedPot === oppPotIndex;
}

ngOnDestroy() {
  if (this.highlightTimeout) {
    clearTimeout(this.highlightTimeout);
  }
  if (this.autoModeTimeout) {
    clearTimeout(this.autoModeTimeout);
  }
}
}