local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local moved={}
for _,b in pairs(s.find_entities_filtered{area={{-70,38},{-55,50}},type="transport-belt"}) do
  for i=1,2 do
    local ok,line=pcall(function() return b.get_transport_line(i) end)
    if ok and line then
      for _,it in pairs(line.get_contents()) do
        local n=p.insert({name=it.name,count=it.count})
        if n>0 then moved[it.name]=(moved[it.name] or 0)+n end
      end
      pcall(function() line.clear() end)
    end
  end
end
local out={}
for n,c in pairs(moved) do out[#out+1]=n.."="..c end
table.sort(out)
return table.concat(out,", ")
