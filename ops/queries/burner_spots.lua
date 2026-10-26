local s=game.surfaces.nauvis
local out={}
local function scan(res,x0,y0,x1,y1)
  local n=0
  for x=x0,x1,2 do
    for y=y0,y1,2 do
      local cx,cy=x+0.5,y+0.5
      if s.can_place_entity{name="burner-mining-drill",position={x=cx,y=cy},direction=0,force=game.forces.player} then
        -- require the 2x2 footprint on resource
        local hit=0
        for _,e in pairs(s.find_entities_filtered{area={{cx-1,cy-1},{cx+1,cy+1}},type="resource"}) do
          if e.name==res then hit=hit+1 end
        end
        if hit>=2 then
          out[#out+1]=string.format("%s (%.1f,%.1f) hit=%d",res,cx,cy,hit)
          n=n+1
          if n>=8 then return end
        end
      end
    end
  end
end
scan("iron-ore",-66,36,-40,62)
scan("copper-ore",-2,60,22,88)
return table.concat(out,"\n")
