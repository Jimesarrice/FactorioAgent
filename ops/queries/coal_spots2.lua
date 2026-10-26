local s=game.surfaces.nauvis
local t={}
for _,y in ipairs({43,45,47,49,51}) do
  for _,x in ipairs({-35,-33,-31,-29,-27}) do
    local found=0; local total=0
    for ox=-1,0.5,0.5 do for oy=-1,0.5,0.5 do local r=s.find_entity("coal",{x+ox,y+oy}) if r then found=found+1; total=total+r.amount end end end
    local free=true
    for _,e in pairs(s.find_entities_filtered{area={{x-1,y-1},{x+1,y+1}}}) do if e.type~="resource" and e.type~="tree" and e.type~="character" then free=false end end
    if total>0 then t[#t+1]=string.format("(%d,%d) coal_tiles=%d total=%d free=%s",x,y,found,total,tostring(free)) end
  end
end
return table.concat(t,"\n")
