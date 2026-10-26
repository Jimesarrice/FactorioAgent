local s = game.surfaces.nauvis
local res = s.find_entities_filtered{type="resource"}
local seen, patches = {}, {}
for _, e in pairs(res) do
  local key = e.position.x..","..e.position.y
  if not seen[key] then
    local q, head = {e}, 1
    seen[key] = true
    local sum, minx, miny, maxx, maxy, name = 0, 1e9, 1e9, -1e9, -1e9, e.name
    while head <= #q do
      local cur = q[head]; head = head + 1
      sum = sum + cur.amount
      minx = math.min(minx, cur.position.x); maxx = math.max(maxx, cur.position.x)
      miny = math.min(miny, cur.position.y); maxy = math.max(maxy, cur.position.y)
      for _, nb in pairs(s.find_entities_filtered{name=name, area={{cur.position.x-1.5,cur.position.y-1.5},{cur.position.x+1.5,cur.position.y+1.5}}}) do
        local nk = nb.position.x..","..nb.position.y
        if not seen[nk] then seen[nk] = true; q[#q+1] = nb end
      end
    end
    patches[#patches+1] = {name=name, amount=sum, count=#q,
      cx=(minx+maxx)/2, cy=(miny+maxy)/2, minx=minx, miny=miny, maxx=maxx, maxy=maxy,
      w=maxx-minx+1, h=maxy-miny+1}
  end
end
local lines = {}
table.sort(patches, function(a,b) return a.amount > b.amount end)
for i=1, math.min(#patches, 40) do
  local p = patches[i]
  lines[#lines+1] = string.format("%s amount=%d tiles=%d center=(%.1f,%.1f) box=(%.1f,%.1f)-(%.1f,%.1f) size=%dx%d",
    p.name, p.amount, p.count, p.cx, p.cy, p.minx, p.miny, p.maxx, p.maxy, p.w, p.h)
end
return table.concat(lines, "\n")
