import unittest
from poker_sim.engine.pots import Pot, distribute_pots

class PotAwardTests(unittest.TestCase):
    def test_main_and_side_pots_can_have_different_winners(self):
        pots=[Pot(300,("short","middle","deep")),Pot(200,("middle","deep")),Pot(100,("deep",))]
        ranks={"short":(8,14),"middle":(7,14,13),"deep":(8,13)}
        awards=distribute_pots(pots,ranks,["short","middle","deep"])
        self.assertEqual([a.winners for a in awards],[("short",),("deep",),("deep",)])
        self.assertEqual([a.payouts for a in awards],[{"short":300},{"deep":200},{"deep":100}])
        self.assertEqual(sum(sum(a.payouts.values()) for a in awards),600)

    def test_tied_main_pot_and_odd_chip_follow_seat_order(self):
        awards=distribute_pots([Pot(101,("a","b","c"))],{"a":(8,9),"b":(8,9),"c":(7,14,13)},["b","a","c"])
        self.assertEqual(awards[0].winners,("a","b"))
        self.assertEqual(awards[0].payouts,{"b":51,"a":50})

    def test_ineligible_stronger_player_cannot_win(self):
        ranks={"live1":(7,14,13),"live2":(6,14,13),"folded":(8,14)}
        award=distribute_pots([Pot(100,("live1","live2"))],ranks,["live1","live2","folded"])[0]
        self.assertEqual(award.winners,("live1",))
        self.assertEqual(award.payouts,{"live1":100})

    def test_rejects_pot_without_ranked_eligible_player(self):
        with self.assertRaisesRegex(ValueError,"no eligible player"):
            distribute_pots([Pot(100,("missing",))],{},["missing"])

    def test_each_side_pot_is_split_independently(self):
        pots=[Pot(5,("a","b")),Pot(8,("b","c"))]
        ranks={"a":(8,5),"b":(8,5),"c":(7,14,13)}
        awards=distribute_pots(pots,ranks,["a","b","c"])
        self.assertEqual(awards[0].payouts,{"a":3,"b":2})
        self.assertEqual(awards[1].payouts,{"b":8})

if __name__=="__main__": unittest.main()
