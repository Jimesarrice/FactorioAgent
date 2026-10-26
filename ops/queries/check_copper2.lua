local s=game.surfaces.nauvis
local out={}
local function report(name,x,y,d)
  local ok=s.can_place_entity{name=name,position={x=x,y=y},direction=d,force=game.forces.player}
  local es=s.find_entities_filtered{area={{x-0.6,y-0.6},{x+0.6,y+0.6}}}
  local names={}
  for _,e in pairs(es) do names[#names+1]=e.name end
  out[#out+1]=string.format("%s(%.1f,%.1f,d%d) can=%s near=%s",name,x,y,d,tostring(ok),table.concat(names,","))
end
report("electric-mining-drill",16.5,60.5,8)
report("small-electric-pole",14.5,60.5,0)
report("small-electric-pole",18.5,60.5,0)
-- count copper in the candidate drilling area
local n=0
for _,e in pairs(s.find_entities_filtered{area={{15,59},{19,63}},type="resource"}) do n=n+1 end
out[#out+1]="copper entities in area="..n
return table.concat(out,"\n")
