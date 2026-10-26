local s=game.surfaces.nauvis
local out={}
local dirs={{0,0,-1},{4,1,0},{8,0,1},{12,-1,0}}
local function try(res,cx,cy)
  if not s.can_place_entity{name="electric-mining-drill",position={x=cx,y=cy},force=game.forces.player} then return nil end
  local n=0
  for _,e in pairs(s.find_entities_filtered{area={{cx-1.5,cy-1.5},{cx+1.5,cy+1.5}},type="resource"}) do
    if e.name==res then n=n+1 end
  end
  if n<3 then return nil end
  for _,d in ipairs(dirs) do
    local dropx,dropy=cx+d[2]*1.85,cy+d[3]*1.85
    for fx=math.floor(dropx)-1,math.floor(dropx)+1 do
      for fy=math.floor(dropy)-1,math.floor(dropy)+1 do
        if math.abs(dropx-fx)<=1 and math.abs(dropy-fy)<=1 then
          if s.can_place_entity{name="stone-furnace",position={x=fx,y=fy},force=game.forces.player} then
            return {cx=cx,cy=cy,dir=d[1],fx=fx,fy=fy,dropx=dropx,dropy=dropy,ore=n}
          end
        end
      end
    end
  end
  return nil
end
for _,cfg in ipairs({{"iron-ore",-55,50,18},{"copper-ore",14,66,18}}) do
  local res,cx,cy,rad=cfg[1],cfg[2],cfg[3],cfg[4]
  local found=0
  for x=cx-rad,cx+rad do
    for y=cy-rad,cy+rad do
      local r=try(res,x+0.5,y+0.5)
      if r then
        out[#out+1]=string.format("%s drill=(%.1f,%.1f) dir=%d furnace=(%d,%d) ore=%d",res,r.cx,r.cy,r.dir,r.fx,r.fy,r.ore)
        found=found+1
        if found>=12 then break end
      end
    end
    if found>=12 then break end
  end
end
return table.concat(out,"\n")
