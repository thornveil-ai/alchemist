-- metatables, OO, coroutines, error handling, pcall
local Vec = {}
Vec.__index = Vec
Vec.__add = function(a, b) return setmetatable({x=a.x+b.x, y=a.y+b.y}, Vec) end
Vec.__tostring = function(v) return "("..v.x..","..v.y..")" end
function Vec.new(x, y) return setmetatable({x=x, y=y}, Vec) end
function Vec:len() return math.sqrt(self.x^2 + self.y^2) end
local a, b = Vec.new(1, 2), Vec.new(3, 4)
print(tostring(a + b), (Vec.new(3,4)):len())

local co = coroutine.create(function(n)
  for i = 1, n do coroutine.yield(i * i) end
  return "done"
end)
local out = {}
for _ = 1, 4 do local ok, v = coroutine.resume(co, 3); out[#out+1] = tostring(v) end
print(table.concat(out, ","), coroutine.status(co))

print(pcall(function() error("boom") end))
print(pcall(function() return 1 + nil end))
print(pcall(function() return 42 end))
local ok, err = pcall(function() error({code=7}) end)
print(ok, type(err), err.code)
print(select(2, xpcall(function() error("x") end, function(e) return "handled:"..e end)))
