local s=game.surfaces.nauvis
local drops={{-55.5,47.6},{6.5,57.6}}
local out={}
for _,d in ipairs(drops) do
  out[#out+1]=string.format("drop %.1f,%.1f",d[1],d[2])
  for cx=math.floor(d[1])-2,math.floor(d[1])+2 do
    for cy=math.floor(d[2])-2,math.floor(d[2])+2 do
      local ok=s.can_place_entity{name="stone-furnace",position={x=cx,y=cy},force=game.forces.player}
      if ok then
        -- check 2x2 footprint contains the drop point (half-open tiles)
        if math.abs(d[1]-cx)<=1 and math.abs(d[2]-cy)<=1 then
          out[#out+1]=string.format("  center=(%d,%d)",cx,cy)
        end
      end
    end
  end
end
return table.concat(out,"\n")
