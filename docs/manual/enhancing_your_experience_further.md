---
title: Enhancing Your Experience Further
slug: enhancing-experience
category: setup
tags: [setup, advanced, editor]
source: paraphrased from official Advanced Setup and Editor documentation
last_updated: 2025-09-24
---

# Enhancing Your Experience Further

In this guide:

- Advanced Game Setup
- Add or Remove Leagues
- Detail Level
- Custom Screen Flow
- Pre-Game Editor
- In-Game Editor
- Achievements

If you want to go beyond Quick Start, the Advanced Setup and Editor tools give you fine-grained control over what appears in your save, how much detail is simulated and what tools are available while you play.

## Advanced Game Setup

Choose Advanced Setup to control nation and league selection, database size, realism options and several global toggles before creating your save. The `Add / Remove Leagues` dialog is the usual starting point: pick nations, set which leagues are Playable vs View-Only and choose how many levels in each country are loaded.

Loading more leagues increases realism (more players, teams and transfers) but slows estimated game speed. Database sizes are typically described as Small / Medium / Large with thousands more players in larger databases. Use the Advanced Database filter to include every player from particular nations or by nationality if you require precision.

### Advanced Options

Eight additional checkboxes let you tweak the world further:

- Use Fake Players and Staff — generate a fictional world rather than real names.
- Do not use Real Fixtures — create fictional schedules for leagues that otherwise use real-life fixtures.
- Do not Add Key Staff — prevents automatic insertion of key backroom roles for teams that lack them.
- Add Players to Playable Teams — fills out undersized squads so teams can start the season.
- Disable First Transfer Window Activity — prevents early real-world transfers from occurring in the first window.
- Disable Player Attribute Masking — reveal all attributes immediately (disable ‘Fog of War’).
- Prevent control of teams with managers in place — only allow vacant clubs to be taken.
- Prevent use of the In-Game Editor — disallow the In-Game Editor in this save (irreversible for that save).

Use these to shape the balance between realism, challenge and convenience.

## Add or Remove Leagues

Leagues may be added or removed during a save (newly added leagues become active when their next season starts). Removing a league is permanent for the following season and may affect affiliated competitions or player movement.

Be mindful: adding nations and divisions increases the number of players and staff present in the database and will impact load time and runtime performance.

## Detail Level

The Detail Level controls which competitions are fully generated (full match engine) and which are simulated via the quick match engine. You can set this per competition or choose `All` / `None`. This is the primary lever to improve performance on slower hardware while maintaining full detail for competitions you care about.

## Custom Screen Flow

Screen Flow (Preferences → Screen Flow) lets you configure screens to be shown automatically at intervals during a save (for example, show Championship → Overview | Stages every week). It’s a lightweight automation system that helps you stay informed without manual navigation and is configured on a per-save basis.

Note: Screen Flow only appears for loaded saved games and will stop processing during Morning if configured to do so for a given flow entry.

## Pre-Game Editor

The Pre-Game Editor is a separate, powerful application to edit or create database objects before starting a save. Use it to create or modify competitions, people, clubs and more.

Typical workflow:

1. File → Load Database (choose the official DB release).
2. Select an object category (People, Clubs, Competitions).
3. Search or add an object and `Edit` its fields (Personal details, Attributes, History, Contracts, Achievements).
4. Save Editor Data As → place the file in the Editor Data folder so the game can include it during new game creation.

Editor Data Files appear in Advanced Setup under `Editor Data` for inclusion. Beware of conflicts where multiple files edit the same object — the editor flags these for resolution.

## In-Game Editor

The In-Game Editor is a paid toggle (platform-specific) that allows real-time edits inside a save. Once enabled you can `Start Editing` from the Actions menu to change visible attributes and many hidden values live.

Use it sparingly: it’s convenient for correcting issues, testing scenarios, or making narrative changes, but changes are immediate and can impact the integrity of long-term saves.

## Achievements

Achievements exist on platform layers (e.g., Steam) and reward specific milestones and challenges. Check your platform’s achievements screen to see goals and track progress across careers.

---

If you’d like I can:

- Add this page to the manual index (`docs/manual/README.md`) and include Editor/Detail Level anchors.
- Generate an `Advanced Setup` quick-reference card listing recommended settings for different hardware tiers.
