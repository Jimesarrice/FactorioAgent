local s=game.surfaces.nauvis
local out={}
local pump={x=335.5,y=437.5}
-- find boiler/engine positions within 12 tiles
for bx=math.floor(pump.x)-8,math.floor(pump.x)+8 do
  for by=math.floor(pump.y)-8,math.floor(pump.y)+8 do
    if s.can_place_entity{name="boiler",position={x=bx,y=by},direction=0,force=game.forces.player} then
      for _,off in ipairs({{0,-3.5},{0,3.5},{-3.5,0},{3.5,0}}) do
        local ex,ey=bx+off[1],by+off[2]
        if s.can_place_entity{name="steam-engine",position={x=ex,y=ey},direction=0,force=game.forces.player} then
          local d=math.abs(bx-pump.x)+math.abs(by-pump.y)
          if d<=12 then
            -- check a pipe path roughly; just report
            out[#out+1]=string.format("boiler=(%d,%d) engine=(%.1f,%.1f) md=%d",bx,by,ex,ey,d)
            if #out>=8 then return table.concat(out,"\n") end
          end
        end
      end
    end
  end
end
return table.concat(out,"\n")
