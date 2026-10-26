local s=game.surfaces.nauvis
local out={}
local n=0
for x=300,380 do
  for y=400,460 do
    if s.can_place_entity{name="oil-refinery",position={x=x,y=y},force=game.forces.player} then
      out[#out+1]="refinery "..x..","..y; n=n+1
      if n>=5 then break end
    end
  end
  if n>=5 then break end
end
out[#out+1]="--- chem"
n=0
for x=300,380 do
  for y=400,460 do
    if s.can_place_entity{name="chemical-plant",position={x=x,y=y},force=game.forces.player} then
      out[#out+1]="chem "..x..","..y; n=n+1
      if n>=8 then return table.concat(out,"\n") end
    end
  end
end
return table.concat(out,"\n")
