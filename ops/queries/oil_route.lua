local s=game.surfaces.nauvis
local ax,ay,bx,by=-10,55,350,435
local out={}
out[#out+1]="route samples every 10 tiles:"
for i=0,55 do
  local t=i/55
  local x,y=ax+(bx-ax)*t,ay+(by-ay)*t
  local tile=s.get_tile(math.floor(x),math.floor(y))
  local cliffs=#s.find_entities_filtered{area={{x-4,y-4},{x+4,y+4}},type="cliff"}
  local water=0
  for dx=-2,2 do for dy=-2,2 do
    local tt=s.get_tile(math.floor(x)+dx,math.floor(y)+dy)
    if tt and (tt.name=="water" or tt.name=="deepwater") then water=water+1 end
  end end
  out[#out+1]=string.format("t=%.2f (%.0f,%.0f) tile=%s water=%d cliffs=%d",t,x,y,tile and tile.name or "?",water,cliffs)
end
-- oil patch nearest pumpjack list
out[#out+1]="--- crude oil patches"
local oil=s.find_entities_filtered{name="crude-oil"}
local seen={}
for _,e in ipairs(oil) do
  local k=e.position.x..","..e.position.y
  if not seen[k] then
    seen[k]=true
    out[#out+1]=string.format("oil @(%.1f,%.1f) amount=%d",e.position.x,e.position.y,e.amount)
  end
end
return table.concat(out,"\n")
