local s=game.surfaces.nauvis
local out={}
for x=-30,12 do
  for y=44,56 do
    local ok=s.can_place_entity{name="stone-furnace",position={x=x,y=y},force=game.forces.player}
    if ok then out[#out+1]=string.format("%d,%d",x,y) end
  end
end
return table.concat(out," ")
