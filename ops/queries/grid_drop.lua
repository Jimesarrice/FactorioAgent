local s=game.surfaces.nauvis
local out={}
for _,d in ipairs({{-55.5,47.6},{6.5,57.6}}) do
  out[#out+1]=string.format("DROP %.1f,%.1f",d[1],d[2])
  for xi=-2,1 do
    for yi=-2,1 do
      local x,y=d[1]+xi+0.5,d[2]+yi+0.5
      local ok=s.can_place_entity{name="stone-furnace",position={x=x,y=y},force=game.forces.player}
      if ok then out[#out+1]=string.format(" furnace(%.1f,%.1f)",x,y) end
    end
  end
  for xi=-1,1 do
    for yi=-1,1 do
      local x,y=d[1]+xi+0.5,d[2]+yi+0.5
      local ok=s.can_place_entity{name="wooden-chest",position={x=x,y=y},force=game.forces.player}
      if ok then out[#out+1]=string.format(" chest(%.1f,%.1f)",x,y) end
    end
  end
end
return table.concat(out,"\n")
