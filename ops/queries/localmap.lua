local s=game.surfaces.nauvis
local x0,y0,x1,y1,step=-300,40,-20,260,5
local lines={}
for y=y0,y1,step do
  local row={}
  for x=x0,x1,step do
    local ch="."
    local ok,t=pcall(function() return s.get_tile(x,y) end)
    if not ok or not t or not t.valid then ch="?"
    elseif t.name=="water" or t.name=="deepwater" then ch="~" end
    if #s.find_entities_filtered{area={{x-1,y-1},{x+1,y+1}},type="cliff"}>0 and ch=="." then ch="#" end
    if math.abs(x-(-179))<5 and math.abs(y-132)<5 then ch="P" end
    row[#row+1]=ch
  end
  lines[#lines+1]=string.format("%4d %s",y,table.concat(row))
end
return table.concat(lines,"\n")
