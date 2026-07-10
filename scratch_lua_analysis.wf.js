export const meta = {
  name: 'lua-analysis',
  description: 'Parallel analysis of all Lua 5.4 modules -> translation DAG + oracle plan',
  phases: [
    { title: 'Analyze', detail: 'one agent per Lua .c module, structured extraction' },
    { title: 'Synthesize', detail: 'build dependency DAG + bottom-up translation order + first batch' },
  ],
}

const DIR = 'C:/Users/jesse/projects/alchemist/subjects/lua'
const MODULES = [
  'lapi','lauxlib','lbaselib','lcode','lcorolib','lctype','ldblib','ldebug',
  'ldo','ldump','lfunc','lgc','liolib','llex','lmathlib','lmem','loadlib',
  'lobject','lopcodes','loslib','lparser','lstate','lstring','lstrlib','ltable',
  'ltablib','ltm','lundump','lutf8lib','lvm','lzio',
]

const MODULE_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['module','loc','public_functions','depends_on_modules','complexity_classes','standalone_oracle_ready','translation_difficulty','notes'],
  properties: {
    module: { type: 'string' },
    loc: { type: 'number' },
    public_functions: {
      type: 'array',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['name','signature','needs_lua_State','differentially_testable'],
        properties: {
          name: { type: 'string' },
          signature: { type: 'string' },
          needs_lua_State: { type: 'boolean' },
          differentially_testable: { type: 'boolean' },
        },
      },
    },
    depends_on_modules: { type: 'array', items: { type: 'string' } },
    complexity_classes: { type: 'array', items: { type: 'string' } },
    standalone_oracle_ready: { type: 'boolean' },
    translation_difficulty: { type: 'string', enum: ['trivial','easy','moderate','hard','extreme'] },
    notes: { type: 'string' },
  },
}

phase('Analyze')
const analyses = await parallel(MODULES.map(m => () =>
  agent(
    `You are analyzing one C module of the Lua 5.4 interpreter for an automated ` +
    `C->safe-Rust translator that verifies each function byte-exact against the ` +
    `compiled C (differential fuzzing).\n\n` +
    `Read the file ${DIR}/${m}.c (and peek at ${DIR}/${m}.h if it exists).\n\n` +
    `Report, as structured output:\n` +
    `- module: "${m}"\n` +
    `- loc: line count of the .c\n` +
    `- public_functions: the LUAI_FUNC / exported functions. For each: name, full C ` +
    `signature, needs_lua_State (true if it takes lua_State* or touches global VM state), ` +
    `and differentially_testable (true if it is a pure-ish fn whose output is fully ` +
    `determined by its args and can be fuzzed standalone with a compiled-C oracle — ` +
    `e.g. a number parser, a hash, a table op on a constructed input; false if it needs ` +
    `the live VM / GC / coroutine scheduler to mean anything).\n` +
    `- depends_on_modules: which OTHER Lua modules (by short name like "lobject","lmem") ` +
    `this one calls into. Bottom-up order depends on this being accurate.\n` +
    `- complexity_classes: any of [goto, computed_goto, setjmp_longjmp, union, ` +
    `function_pointer, recursion, macro_heavy, float_math, unsafe_ptr_arith, varargs]. ` +
    `Only list ones actually present.\n` +
    `- standalone_oracle_ready: can AT LEAST ONE function here be differentially verified ` +
    `without standing up the whole interpreter?\n` +
    `- translation_difficulty: trivial|easy|moderate|hard|extreme (extreme = lvm dispatch).\n` +
    `- notes: one or two sentences on the sharpest translation risk.`,
    { label: `analyze:${m}`, phase: 'Analyze', schema: MODULE_SCHEMA }
  )
))

const ok = analyses.filter(Boolean)
log(`analyzed ${ok.length}/${MODULES.length} modules`)

phase('Synthesize')
const DAG_SCHEMA = {
  type: 'object',
  additionalProperties: false,
  required: ['translation_order','first_batch','oracle_strategy','new_walls_vs_smaz','risk_summary'],
  properties: {
    translation_order: {
      type: 'array',
      description: 'modules in bottom-up dependency order (leaves first)',
      items: { type: 'string' },
    },
    first_batch: {
      type: 'array',
      description: 'independent leaf modules that can translate in parallel FIRST',
      items: {
        type: 'object',
        additionalProperties: false,
        required: ['module','why','first_functions'],
        properties: {
          module: { type: 'string' },
          why: { type: 'string' },
          first_functions: { type: 'array', items: { type: 'string' } },
        },
      },
    },
    oracle_strategy: { type: 'string' },
    new_walls_vs_smaz: { type: 'array', items: { type: 'string' } },
    risk_summary: { type: 'string' },
  },
}

const synthesis = await agent(
  `You are planning the bottom-up translation of the ENTIRE Lua 5.4 interpreter ` +
  `to safe Rust, verified byte-exact-or-refused. Here are structured analyses of ` +
  `all ${ok.length} library modules (JSON):\n\n${JSON.stringify(ok)}\n\n` +
  `smaz (a small codec with a forward goto + hash codebook) is already conquered ` +
  `byte-exact. Produce the master plan:\n` +
  `- translation_order: ALL modules in a valid bottom-up dependency order (a module ` +
  `comes after everything in its depends_on_modules). Leaves first.\n` +
  `- first_batch: the independent LEAF modules (no unmet deps) we should translate ` +
  `FIRST, ideally in parallel. For each, name the concrete first functions to target ` +
  `(prefer differentially_testable ones).\n` +
  `- oracle_strategy: how to get a compiled-C differential oracle for a module that is ` +
  `part of a 26k-LOC library (scoping the build, stubbing lua_State where a fn is pure).\n` +
  `- new_walls_vs_smaz: capability walls Lua introduces that smaz did not ` +
  `(computed goto, setjmp/longjmp, unions, ...), each with the module where it first bites.\n` +
  `- risk_summary: the 2-3 things most likely to block reaching 100%.`,
  { label: 'synthesize:dag', phase: 'Synthesize', schema: DAG_SCHEMA }
)

return { analyzed: ok.length, synthesis, per_module: ok }
