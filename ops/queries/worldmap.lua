local s=game.surfaces.nauvis
local lines={}
for y=-100,700,10 do
  local row={}
  for x=-100,700,10 do
    local t=s.get_tile(x,y)
    local ch="."
    if not t then ch="?"
    elseif t.name=="water" or t.name=="deepwater" then ch="~"
    end
    if math.abs(x-350)<=20 and math.abs(y-470)<=40 then ch="o" end
    if math.abs(x+10)<=10 and math.abs(y-55)<=10 then ch="B" end
    if #s.find_entities_filtered{area={{x-2,y-2},{x+2,y+2}},type="cliff"}>0 and ch=="." then ch="#" end
    row[#row+1]=ch
  end
  lines[#lines+1]=string.format("%4d %s",y,table.concat(row))
end
return table.concat(lines,"\n")
