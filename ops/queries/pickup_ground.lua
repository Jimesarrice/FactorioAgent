local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local areas={{{-80,30},{-20,70}},{{-10,55},{30,90}}}
local moved={}
for _,area in ipairs(areas) do
  for _,e in pairs(s.find_entities_filtered{area=area,type="item-entity"}) do
    local st=e.stack
    local n=p.insert(st)
    if n and n>0 then
      moved[st.name]=(moved[st.name] or 0)+n
      if n>=st.count then e.destroy() else st.count=st.count-n end
    end
  end
end
local out={}
for n,c in pairs(moved) do out[#out+1]=n.."="..c end
table.sort(out)
return "picked "..table.concat(out,", ")
