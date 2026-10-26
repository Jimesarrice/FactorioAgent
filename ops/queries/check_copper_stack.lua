local s=game.surfaces.nauvis
local out={}
local function report(name,x,y,d)
  local ok=s.can_place_entity{name=name,position={x=x,y=y},direction=d,force=game.forces.player}
  local es=s.find_entities_filtered{area={{x-0.6,y-0.6},{x+0.6,y+0.6}}}
  local names={}
  for _,e in pairs(es) do names[#names+1]=e.name end
  out[#out+1]=string.format("%s(%.1f,%.1f,d%d) can=%s near=%s",name,x,y,d,tostring(ok),table.concat(names,","))
end
report("electric-mining-drill",16.5,68.5,0)
report("stone-furnace",16,66,0)
report("small-electric-pole",19,68,0)
report("electric-mining-drill",16.5,72.5,0)
report("stone-furnace",16,70,0)
report("small-electric-pole",19,72,0)
local function cnt(x,y)
  local n=0
  for _,e in pairs(s.find_entities_filtered{area={{x-1.5,y-1.5},{x+1.5,y+1.5}},type="resource"}) do n=n+1 end
  return n
end
out[#out+1]="copper at 68.5="..cnt(16.5,68.5).." at72.5="..cnt(16.5,72.5)
return table.concat(out,"\n")
