import time
from collections import Counter

from django.core.management.base import BaseCommand

from ai_module.services import SEVERITY_LEVELS, classify_incident

RANK = {name.lower(): index for index, name in enumerate(SEVERITY_LEVELS)}

# (category, description, expected severity). Labels are the author's judgement:
# review them before quoting the accuracy figure in the report.
CASES = [
  ('Fire', 'Smell of burnt toast in the staff kitchen, no smoke or flames, already ventilated.', 'low'),
  ('Fire', 'Fire extinguisher in corridor B has an expired inspection tag.', 'low'),
  ('Medical', 'A student has a mild headache and asks for paracetamol, otherwise fine.', 'low'),
  ('Medical', 'Small paper cut on a finger in the library, bleeding stopped.', 'low'),
  ('Security', 'Unfamiliar bicycle left chained to the railing for two days.', 'low'),
  ('Security', 'Student lost their ID card and wants it reported.', 'low'),
  ('Mental Health', 'A first-year student feels stressed before exams and would like to talk to a counsellor this week.', 'low'),
  ('Mental Health', 'Colleague mentions feeling a bit down lately but is working normally.', 'low'),
  ('Fire', 'Alarm panel in the hostel shows a minor fault light, no alarm sounding.', 'low'),
  ('Security', 'Lecture hall door lock is stiff and hard to open.', 'low'),
  ('Fire', 'Small bin fire in the corridor was put out with an extinguisher, some smoke remains.', 'medium'),
  ('Fire', 'Smoke is coming from an electrical socket in room 12, no flames visible.', 'medium'),
  ('Medical', 'Student twisted an ankle on the stairs and cannot put weight on it.', 'medium'),
  ('Medical', 'Staff member feels dizzy and nauseous after skipping meals, sitting down and conscious.', 'medium'),
  ('Security', 'Two people were seen trying car door handles in the staff parking lot.', 'medium'),
  ('Security', 'Laptop stolen from the computer lab, the thief already left the building.', 'medium'),
  ('Mental Health', 'A student has been crying in the library for an hour and says they cannot cope with coursework.', 'medium'),
  ('Mental Health', 'Resident has not slept for days and feels overwhelmed, but is calm and talking.', 'medium'),
  ('Medical', 'Child has a high fever and vomiting in the estate day-care, parents not yet reached.', 'medium'),
  ('Security', 'Verbal argument between two groups at the gate, no weapons, crowd gathering.', 'medium'),
  ('Fire', 'Fire in a laboratory storeroom, flames visible and spreading, people evacuating.', 'high'),
  ('Fire', 'Kitchen fire in the cafeteria, flames reaching the ceiling, staff evacuated.', 'high'),
  ('Medical', 'Student collapsed during sports, conscious but with chest pain and short of breath.', 'high'),
  ('Medical', 'Worker fell from a ladder and is bleeding heavily from the leg.', 'high'),
  ('Security', 'A man with a knife is threatening staff at the reception.', 'high'),
  ('Security', 'Intruder has broken into the dormitory and is going door to door.', 'high'),
  ('Mental Health', 'Student says they want to hurt themselves and is alone in their room, has not harmed themselves yet.', 'high'),
  ('Medical', 'Several students have severe food poisoning after the cafeteria lunch, vomiting and fainting.', 'high'),
  ('Fire', 'Gas cylinder leaking in the canteen, strong smell of gas, people still inside.', 'high'),
  ('Security', 'Fight at the hostel has left two people injured, attackers still on site.', 'high'),
  ('Fire', 'Building on fire, people trapped on the third floor calling for help from the windows.', 'critical'),
  ('Fire', 'Explosion in the chemistry lab, fire spreading, several people not accounted for.', 'critical'),
  ('Medical', 'Person unconscious and not breathing after collapsing in the hall.', 'critical'),
  ('Medical', 'Severe road accident at the campus gate, several people badly injured and trapped in a vehicle.', 'critical'),
  ('Security', 'Armed attacker has entered the building and is shooting.', 'critical'),
  ('Security', 'Hostage situation in the administration block, gunman threatening to kill.', 'critical'),
  ('Mental Health', 'Student is on the roof ledge threatening to jump right now.', 'critical'),
  ('Mental Health', 'Patient has taken a large quantity of tablets and is drowsy and unresponsive.', 'critical'),
  ('Medical', 'Student with a swollen face is struggling to breathe after eating peanuts, no auto-injector.', 'critical'),
  ('Fire', 'Hospital oxygen store on fire next to the ICU, patients being moved out.', 'critical'),
]


def _score(expected, got, source):
  if source == 'fallback' or got not in RANK:
    return False, False
  gap = abs(RANK[expected] - RANK[got])
  return gap == 0, gap <= 1


class Command(BaseCommand):
  help = 'Run labelled sample incidents through classify_incident and report severity accuracy.'

  def add_arguments(self, parser):
    parser.add_argument('--delay', type=float, default=4.0,
                        help='Seconds between calls, to respect free-tier rate limits.')

  def handle(self, *args, **options):
    exact = near = 0
    sources = Counter()
    misses = []
    for category, text, expected in CASES:
      result = classify_incident(text, category)
      got = result['severity'].lower()
      sources[result['source']] += 1
      hit, close = _score(expected, got, result['source'])
      exact += hit
      near += close
      if not hit:
        misses.append(f"  expected {expected:<8} got {got:<8} [{result['source']}] {text[:70]}")
      time.sleep(options['delay'])

    total = len(CASES)
    self.stdout.write(f'Cases: {total}')
    self.stdout.write(f'Answered by: {dict(sources)}')
    self.stdout.write(f'Exact severity match: {exact}/{total} = {exact / total:.0%}')
    self.stdout.write(f'Within one level:     {near}/{total} = {near / total:.0%}')
    self.stdout.write('Target in the proposal: above 85%')
    if misses:
      self.stdout.write('Misses:')
      self.stdout.write('\n'.join(misses))
