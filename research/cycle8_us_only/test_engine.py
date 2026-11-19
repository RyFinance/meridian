import numpy as np
from research.cycle8_us_only import core

def sim(R,w,L=1.,rates=None,o=None,X=None):
 R=np.array(R,float)[None];n=R.shape[1]
 return core.simulate(R,np.zeros((1,n,1)) if X is None else np.array(X,float)[None],np.zeros((1,n,2)) if rates is None else np.array(rates,float)[None],np.array(w),np.zeros(1) if o is None else np.array(o),L,np.zeros(len(w)),np.zeros(1),np.ones(n,bool))
def test_unlevered_compounds():
 z=sim([[.1],[-.2]],[1]);assert np.isclose(z['wealth'][0,-1],.88)
def test_margin_loan_financing():
 z=sim([[.1]],[1],2.,[[.01,0]]);assert np.isclose(z['wealth'][0,-1],1.19)
def test_liquidation_not_ignored():
 z=sim([[-.4],[.5]],[1],2.)
 assert z['calls'][0]==1 and z['wealth'][0,1]<.2
 assert z['wealth'][0,-1]<.4

def test_p4_base_borrows_and_can_call():
 z=sim([[-.9]],[1.2]);assert z['ruined'][0]
 z=sim([[-.8]],[1.2]);assert z['calls'][0]==1

def test_ruin_absorbing():
 z=sim([[-.6],[10.]],[1],2.);assert z['ruined'][0] and z['wealth'][0,-1]==0

def test_overlay_no_duplicate_cash():
 z=sim([[.1]],[1],o=[.5],X=[[.04]]);assert np.isclose(z['wealth'][0,-1],1.12)
