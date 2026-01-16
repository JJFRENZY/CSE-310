# Command Battle (Game Framework Module)

## Overview
This project is a 2D command-planning battle game created for CSE 310 (Applied Programming) as part of the Game Framework module. Battles last 12 turns and both fighters plan their commands (Attack, Block, Counter) before the battle begins. The game then resolves each turn using defined interaction rules.

## Game Rules (Summary)
- 12 turns total (commands are planned before battle)
- Each fighter starts with 3 Hearts
- Commands per fighter:
  - Attack (A): 5 uses, deals 1 damage if successful
  - Block (B): 2 uses, reduces incoming attack to 0.5 damage
  - Counter (C): 1 use, reflects 1 damage if opponent attacks; if opponent doesn't attack, the counter user skips the next turn
- Attack vs Attack: both fail (no damage)
- If no one is knocked out after 12 turns: Sudden Death (50/50 KO chance)

## Development Environment
- Language: Python 3
- Framework: Pygame
- Editor: Visual Studio Code

## How to Run
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
