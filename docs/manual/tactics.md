---
title: Tactics
slug: tactics
category: match
tags: [tactics, match, formations]
source: paraphrased from official Tactics documentation
last_updated: 2025-09-24
---

# Tactics

In this guide:

- Tactical Templates
- Mentalities
- Team Fluidity
- Formations
- Roles and Duties
- Team Instructions
- Player Instructions
- Opposition Instructions
- Set Pieces
- Saving and Exporting Routines
- Match Plans
- Captains

This page explains the building blocks of a tactic and how to translate ideas into on-pitch behaviour.

## Tactical Templates

Templates are ready-made tactic foundations that apply a set of team and player instructions for a clear style (for example: counter-attacking, possession, high press). They’re intended as starting points — inspect and tweak the resulting instructions to suit your squad.

## Mentalities

Think of Mentality as a 1–20 scale where Very Defensive sits low and Very Attacking sits high. The chosen Mentality adjusts several hidden tactical parameters (press intensity, line of engagement, tempo, width, directness, time-wasting) and also influences how players on Automatic duties behave.

Choosing a Mentality is a macro decision that interacts with the tactical instructions you set.

## Team Fluidity

Fluidity describes the balance of Attack/Support/Defend duties across the XI. For example, a Balanced setup might have 3 Defend / 4 Support / 3 Attack duties; more Attack duties without compensating Support duties yields a rigid, attacking shape. Fluidity impacts how much individual players roam and how tightly the team works together.

Experiment: increasing Support duties generally produces a more fluid, cooperative team; skewing duties produces more specialised, rigid behaviour.

## Formations

A formation is the defensive shape shown on the tactics screen and the baseline positions players return to out of possession. Choose formations that fit your squad (pick the shape that best uses your strengths) or impose a preferred structure and adapt players to it — both approaches are valid.

Remember: the on-screen formation primarily shows defensive shape; instructions and roles determine movement when in possession.

## Roles and Duties

Each position offers multiple Roles with three Duty options (Attack, Support, Defend). Roles come with their own default instructions and attribute requirements; use `Highlight Key Attributes for Role` on a player profile to see how suitable a player is for a role.

Playing someone in an unfamiliar role is less damaging than playing them out of position, but there are diminishing returns if attributes don’t match. Players do learn roles over time, faster when training and match minutes align with the new role and when coaching quality is high.

## Team Instructions

Team Instructions steer broad behaviour and are grouped into three phases.

IN POSSESSION

- Attacking Width — how wide your attacks are.
- Approach Play — focus passing into space, down flanks or through the middle; Play Out Of Defence is available for building from the back.
- Passing Directness — short, standard or more direct passing.
- Tempo — decision speed and match tempo.
- Time Wasting — higher values slow play and waste time.
- Final Third options — cross types and emphasis on set pieces.
- Dribbling and Creative Freedom — control risk appetite and expression.

IN TRANSITION

- When possession is lost — Counter-Press vs Regroup.
- When possession is won — Counter vs Hold Shape.
- Goalkeeper in possession — distribute quickly or slow down; choose distribution type (to player groups or specific positions).

OUT OF POSSESSION

- Defensive Shape, Line of Engagement and Defensive Line — control vertical compactness and pressing behaviour.
- Defensive Width — how much width you defend.
- Marking/Tackling — Stay On Feet vs Get Stuck In.
- Pressing Trap and Cross Engagement — triggers for forcing play into certain areas and controlling crosses.

These settings must be balanced to produce coherent on-field behaviour.

## Player Instructions

Player instructions fine-tune behaviour for individual players or positions and are grouped by phase:

When Opposition has the Ball — Trigger Press, Mark Tighter, Tackle Harder/Ease Off, Mark Specific Player/Position.

When Team has the Ball — Get Further Forward, Hold Position, Stay Wider, Sit Narrower, Move Into Channels, Roam From Position.

When Player has the Ball — Hold Up Ball, Run Wide With Ball, Cut Inside With Ball.

Passing and Shooting — adjust Passing Directness, Shooting frequency, Dribbling and Crossing frequency/targeting.

Player instructions override or modify defaults from Role/Duty and are useful to cover individual strengths or weaknesses.

## Opposition Instructions

Pre-match Opposition Instructions let you apply position- or player-specific constraints for upcoming matches. Common instructions include Tight Marking, Trigger Press, Tackling style and forcing a player onto their weak foot (`Show onto Foot`). These instructions depend on the comparative attributes and the context of your overall tactic.

## Set Pieces

Set Pieces have detailed defensive and attacking configuration: defensive marking strategies, which posts to mark, how many players remain forward/defend, and attacking delivery choices. Staff recommendations are shown but you may override them.

Identify your best corner, free-kick and throw-in takers by the relevant attributes (Crossing, Long Throws, Penalty Taking, Composure, Strength). Assign multiple takers in ranked order and consider signing specialists if needed.

### Saving and Exporting Routines

You can create, save, load and export set piece routines. Each side and scenario can store multiple routines (limits apply), and routines rotate during matches if more than one exists. Use `Save Routine` and `Load Routine` from the Routine menu to manage them.

## Match Plans

Match Plans are conditional tactic switches that trigger automatically (or are delegated to your Assistant) when certain match scenarios occur — e.g., `Winning by 1+ goal` in `75–85 mins`. A Match Plan can change Tactic, Mentality and apply Touchline Instructions. Plans can be layered to cover many situations but can be overridden by touchline changes during the match.

## Captains

At season start you’ll be asked to confirm a captain and vice-captain. Captains should have leadership and the right personality: Born Leader, Determined, Model Professional, and sufficient experience. A strong captain can raise team performance; a poor pick can hold the team back.

Re-ordering captain hierarchy is done via drag-and-drop in the Captains panel. Changing captaincy mid-season can have social consequences, so choose carefully and have a reason for changes.

---

Would you like me to:

- Add this page to the manual index (`docs/manual/README.md`) with a link to `tactics.md`?
- Split sections into separate pages (e.g., `set_pieces.md`, `player_instructions.md`) and wire cross-links?
- Generate a short printable tactics cheat-sheet (PDF) from these pages? Note: PDF creation requires a local tool such as Pandoc or wkhtmltopdf.
