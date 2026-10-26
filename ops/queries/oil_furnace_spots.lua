local s=game.surfaces.nauvis
local out={}
local n=0
for x=300,400 do
  for y=400,470 do
    local ok=s.can_place_entity{name="stone-furnace",position={x=x,y=y},force=game.forces.player}
    if ok then
      out[#out+1]=x..","..y; n=n+1
      if n>=8 then return table.concat(out," ") end
    end
  end
end
return table.concat(out," ")
