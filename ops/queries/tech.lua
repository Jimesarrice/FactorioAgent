local f = game.forces.player
local done, avail = {}, {}
for name, t in pairs(f.technologies) do
  if t.enabled then
    if t.researched then
      done[#done+1] = name
    else
      local unmet = {}
      for _, p in pairs(t.prerequisites or {}) do
        if not p.researched then unmet[#unmet+1] = p.name end
      end
      avail[#avail+1] = string.format("%s%s", name, #unmet > 0 and (" <- "..table.concat(unmet, ",")) or "")
    end
  end
end
table.sort(done); table.sort(avail)
return "RESEARCHED ("..#done.."):\n"..table.concat(done, ", ").."\n\nAVAILABLE ("..#avail.."):\n"..table.concat(avail, "\n")
