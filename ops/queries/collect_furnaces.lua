local s=game.surfaces.nauvis
local p=game.players["LLM-Bot"]
local inv=p.get_main_inventory()
local byid={}
for _,e in pairs(s.find_entities_filtered{force="player"}) do
  if e.unit_number then byid[e.unit_number]=e end
end
local ids={161,162,163,164,165,166,167,168,169,170,171,172,173,174,175,176,177,178,179,180}
local moved={}
for _,u in ipairs(ids) do
  local e=byid[u]
  if e then
    for i=1,4 do
      local ent_inv=e.get_inventory(i)
      if ent_inv then
        for _,it in pairs(ent_inv.get_contents()) do
          if it.name=="iron-plate" or it.name=="copper-plate" then
            local n=inv.insert({name=it.name,count=it.count})
            if n>0 then ent_inv.remove({name=it.name,count=n}); moved[it.name]=(moved[it.name] or 0)+n end
          end
        end
      end
    end
  end
end
local out={}
for n,c in pairs(moved) do out[#out+1]=n.."="..c end
table.sort(out)
return table.concat(out,", ")
