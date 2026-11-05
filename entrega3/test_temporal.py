"""Prueba adversarial: un partido actual/futuro no altera su historial previo."""
import unittest
import pandas as pd
import numpy as np
from completar_prediccion import history,STATS

class TestTemporal(unittest.TestCase):
    def test_same_date_and_future_are_excluded(self):
        rows=[]
        for date,aces in [('2018-01-01',3),('2018-01-08',4),('2018-01-08',5),('2018-01-15',6)]:
            row={'id':'A','surface':'cemento','fecha':pd.Timestamp(date),'n':1,'wins':1,'valid':1,'valid_rest':1,
                 **{s:10 for s in STATS},'rest_points':60,'rest_won':20,'bp_chances':5,'bp_converted':2}
            row.update(ace=aces,svpt=60,**{'1stIn':40,'2ndWon':12});rows.append(row)
        p=pd.DataFrame(rows);h,_=history(p)
        self.assertEqual(h.iloc[0].n,0)
        self.assertEqual(h.iloc[1].n,1)
        self.assertEqual(h.iloc[1].ace,3)
        self.assertEqual(h.iloc[2].n,3)
        changed=p.copy();changed.loc[changed.fecha>='2018-01-08','ace']=55
        h2,_=history(changed)
        np.testing.assert_array_equal(h.loc[:1,['n','ace']],h2.loc[:1,['n','ace']])
        self.assertEqual(h2.iloc[2].ace,113)

if __name__=='__main__':unittest.main()
