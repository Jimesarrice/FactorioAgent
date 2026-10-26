local s=game.surfaces.nauvis
local out={}
for y=420,436 do
  local bad=0; local list={}
  for x=302,353 do
    if not s.can_place_entity{name="pipe",position={x=x+0.5,y=y+0.5},force=game.forces.player} then bad=bad+1; list[#list+1]=x end
  end
  out[#out+1]=string.format("y=%d bad=%d %s",y+1,bad,table.concat(list,","))
end
-- vertical x=301.5 416.5..428.5
local vb={}
for y=417,428 do
  if not s.can_place_entity{name="pipe",position={x=301.5,y=y+0.5},force=game.forces.player} then vb[#vb+1]=y end
end
out[#out+1]="vertical x301.5 bad="..table.concat(vb,",")
return table.concat(out,"\n")
