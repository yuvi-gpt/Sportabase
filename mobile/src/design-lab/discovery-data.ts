import type { ResultKey } from './mock-results';

export type SportKey = 'Football' | 'Formula 1' | 'Tennis' | 'Cricket' | 'Basketball' | 'NFL';
export type Storyline = { context: string; title: string; description: string; state: string; reports: number; independent: number; resultKey: ResultKey };

export const sports: SportKey[] = ['Football', 'Formula 1', 'Tennis', 'Cricket', 'Basketball', 'NFL'];
export const storylines: Record<SportKey, Storyline[]> = {
  Football: [
    { context: 'Transfer market', title: 'Forward’s future remains unresolved', description: 'Club position and player interest remain central as separate reports describe ongoing talks.', state: 'Developing', reports: 8, independent: 3, resultKey: 'plausible' },
    { context: 'Premier League', title: 'Defensive move gathers independent support', description: 'Multiple reporters identify contact, while no formal agreement has been announced.', state: 'Substantial', reports: 6, independent: 3, resultKey: 'confirmed' },
    { context: 'Squad decision', title: 'Conflicting selection reports persist', description: 'Credible accounts disagree about the final lineup ahead of the next fixture.', state: 'Contested', reports: 4, independent: 2, resultKey: 'contested' },
  ],
  'Formula 1': [
    { context: 'Driver market', title: 'Seat negotiations remain open', description: 'Contract discussions continue while the team considers more than one driver option.', state: 'Developing', reports: 7, independent: 2, resultKey: 'plausible' },
    { context: 'Team development', title: 'Upgrade direction gains technical support', description: 'Separate paddock reports point to the same development priority for the next race.', state: 'Substantial', reports: 5, independent: 3, resultKey: 'opinion' },
    { context: 'Contract', title: 'Extension claim lacks direct attribution', description: 'Repeated coverage offers no team statement or clearly independent sourcing.', state: 'Limited', reports: 4, independent: 1, resultKey: 'limited' },
  ],
  Tennis: [
    { context: 'Player availability', title: 'Tournament status remains uncertain', description: 'Practice reports are encouraging, but no official participation decision has been made.', state: 'Developing', reports: 6, independent: 2, resultKey: 'limited' },
    { context: 'Tour update', title: 'Withdrawal is officially confirmed', description: 'The tournament and player team now describe the same availability outcome.', state: 'Confirmed', reports: 5, independent: 3, resultKey: 'confirmed' },
    { context: 'Coaching team', title: 'Change is reported without named sourcing', description: 'A widely repeated coaching claim still lacks attributable supporting detail.', state: 'Unsupported', reports: 3, independent: 0, resultKey: 'critical' },
  ],
  Cricket: [
    { context: 'Squad selection', title: 'Availability decision remains contested', description: 'Independent reports disagree about whether the player will join the tournament squad.', state: 'Contested', reports: 5, independent: 2, resultKey: 'contested' },
    { context: 'Team management', title: 'Selection policy draws reasoned criticism', description: 'A former captain presents a clearly attributed argument about balance and role clarity.', state: 'Opinion', reports: 4, independent: 1, resultKey: 'opinion' },
    { context: 'Tournament squad', title: 'Replacement receives official clearance', description: 'Board and tournament communications materially resolve the earlier uncertainty.', state: 'Confirmed', reports: 6, independent: 4, resultKey: 'confirmed' },
  ],
  Basketball: [
    { context: 'Trade market', title: 'Exploratory discussions continue', description: 'Reporting identifies mutual interest without establishing a completed transaction.', state: 'Developing', reports: 7, independent: 2, resultKey: 'plausible' },
    { context: 'Player status', title: 'Return timeline remains provisional', description: 'One report offers a target date, but team medical confirmation is absent.', state: 'Limited', reports: 4, independent: 1, resultKey: 'limited' },
    { context: 'Roster move', title: 'Team confirms agreement', description: 'Official communication and independent reporting now align on the transaction.', state: 'Confirmed', reports: 5, independent: 3, resultKey: 'confirmed' },
  ],
  NFL: [
    { context: 'Free agency', title: 'Contract interest is developing', description: 'Several reports identify contact while details of any offer remain unclear.', state: 'Developing', reports: 6, independent: 2, resultKey: 'plausible' },
    { context: 'Injury report', title: 'Weekend availability cannot be assessed', description: 'The current report lacks a diagnosis, practice designation, or team timetable.', state: 'Limited', reports: 3, independent: 1, resultKey: 'limited' },
    { context: 'Depth chart', title: 'Starter decision remains unresolved', description: 'Two established reporters describe opposing outcomes from separate sources.', state: 'Contested', reports: 4, independent: 2, resultKey: 'contested' },
  ],
};

export const acrossSportabase = [
  { label: 'Developing now', sport: 'Football', title: 'Midfield talks gain a second reporting thread', state: '3 new reports', resultKey: 'plausible' as ResultKey },
  { label: 'Confirmed today', sport: 'Tennis', title: 'Official withdrawal resolves availability question', state: 'Official source located', resultKey: 'confirmed' as ResultKey },
  { label: 'Most contested', sport: 'Cricket', title: 'Selection accounts remain materially opposed', state: '2 independent positions', resultKey: 'contested' as ResultKey },
];
