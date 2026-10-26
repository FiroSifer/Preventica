import test from 'node:test';
import assert from 'node:assert/strict';
import {normalize,valid,distance} from '../frontend/geometry.js';
test('coordinates follow actual frame rectangle at different scales',()=>{assert.deepEqual(normalize(250,150,{left:50,top:50,width:400,height:200}),[.5,.5]);assert.deepEqual(normalize(450,250,{left:50,top:50,width:800,height:400}),[.5,.5]);});
test('reject crossed, degenerate and out-of-range polygons',()=>{assert.equal(valid([[0,0],[1,0],[1,1],[0,1]]),true);for(const p of [[[0,0],[1,1],[1,0],[0,1]],[[0,0],[0,0],[1,1]],[[0,0],[2,0],[1,1]],[[0,0],[.5,.5],[1,1]]])assert.equal(valid(p),false);});
test('edge hit detection',()=>assert.equal(distance([.5,.1],[0,0],[1,0]),.1));
