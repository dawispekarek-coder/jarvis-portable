import copy
import unittest
from companion_video_director import audit_plan

class HugMorphologyTests(unittest.TestCase):
    def test_czech_hug_inflections_are_accepted_but_missing_hug_is_rejected(self):
        beats=('setup','approach','entry','reaction','embrace','payoff')
        actions=('Lali ceka u zavrenych dveri',
                 'Pooli jde ke dverim a uchopi kliku',
                 'Pooli otevre dvere a prekroci prah',
                 'Lali vidi Pooliho a ma radost',
                 'Lali objima Pooliho kolem ramen',
                 'Lali a Pooli se usmivaji')
        shots=[]
        for i,(beat,action) in enumerate(zip(beats,actions)):
            shots.append(dict(beat=beat,camera=('WIDE' if i%2==0 else 'CLOSE'),
              setting='domov pokoj',action=action,lali_emotion=('radost' if i>2 else 'zvedavost'),
              pooli_emotion=('radost' if i>3 else 'unava'),lali_pose='stoji',pooli_pose='stoji',
              prop='taska dvere',sound='kroky'))
        plan=dict(title='Vitanie',premise='Pooli jde domu z prace a Lali ho radostne vita',
                  location='domov',shots=shots)
        goal='Pooli prijde domu z prace a Lali ho vita'
        self.assertEqual([],audit_plan(plan,goal))
        no_hug=copy.deepcopy(plan)
        no_hug['shots'][4]['action']='Lali dojde k Poolimu'
        self.assertIn('Zaber 5 musi ukazat skutecne objeti',audit_plan(no_hug,goal))

if __name__=='__main__':unittest.main()