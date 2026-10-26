local s=game.surfaces.nauvis
local out={}
local n=0
for x=-34,-8,2 do
  for y=46,52,2 do
    local cx,cy=x+0.5,y+0.5
    if s.can_place_entity{name="burner-mining-drill",position={x=cx,y=cy},direction=4,force=game.forces.player} then
      local hit=0
      for _,e in pairs(s.find_entities_filtered{area={{cx-1,cy-1},{cx+1,cy+1}},type="resource"}) do
        if e.name=="coal" then hit=hit+1 end
      end
      if hit>=6 then
        out[#out+1]=string.format("(%.1f,%.1f) hit=%d",cx,cy,hit)
        n=n+1
        if n>=12 then return table.concat(out,"\n") end
      end
    end
  end
end
return table.concat(out,"\n")
