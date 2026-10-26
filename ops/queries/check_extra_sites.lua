local s=game.surfaces.nauvis
local sites={
 {"iron-ore",-46,59,4,-44,59},
 {"copper-ore",20,64,0,20,62},
 {"copper-ore",22,66,0,22,64},
 {"iron-ore",-42,58,4,-40,58},
}
local out={}
for _,v in ipairs(sites) do
  local name,cx,cy,dir,fx,fy=v[1],v[2],v[3],v[4],v[5],v[6]
  local function tile_ent(x,y)
    local es=s.find_entities_filtered{area={{x-0.45,y-0.45},{x+0.45,y+0.45}}}
    for _,e in pairs(es) do if e.type~="fish" then return e end end
    return nil
  end
  local pure=true
  for dx=-1,1 do for dy=-1,1 do
    local e=tile_ent(cx+dx,cy+dy)
    if not e or e.type~="resource" or e.name~=name then pure=false end
  end end
  local okd=s.can_place_entity{name="electric-mining-drill",position={x=cx,y=cy},direction=dir,force=game.forces.player}
  local okf=s.can_place_entity{name="stone-furnace",position={x=fx,y=fy},force=game.forces.player}
  out[#out+1]=string.format("%s drill(%.1f,%.1f) pure=%s can=%s furnace(%.1f,%.1f) can=%s",name,cx,cy,tostring(pure),tostring(okd),fx,fy,tostring(okf))
end
return table.concat(out,"\n")
