local s=game.surfaces.nauvis
local out={}
for y=430,460 do
  for x=290,355 do
    if s.can_place_entity{name="small-electric-pole",position={x=x+0.5,y=y+0.5},force=game.forces.player} then
      local de=math.sqrt((x+0.5-296.5)^2+(y+0.5-448.5)^2)
      local dp=math.sqrt((x+0.5-353.5)^2+(y+0.5-435.5)^2)
      if de<=7.5 or dp<=7.5 then
        out[#out+1]=string.format("%.1f,%.1f dE=%.1f dP=%.1f",x+0.5,y+0.5,de,dp)
      end
    end
  end
end
return table.concat(out,"\n")
