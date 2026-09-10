(() => {
  const $ = (sel, root = document) => root.querySelector(sel)
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)]
  const OFFLINE = location.protocol === 'file:'
  const state = {
    health: null,
    tree: [],
    sessions: [],
    tasks: [],
    worktrees: [],
    workflows: [],
    openFiles: [],
    activePath: '',
    expanded: new Set(['src', 'src/codeagent', 'tests']),
    leftView: 'explorer',
    leftOpen: true,
    terminalOpen: true,
    reviewMode: false,
    diff: null,
    ws: null,
    connected: false,
    running: false,
    sessionId: '',
    model: '',
    demo: false,
    tools: [],
    events: [],
    permission: null,
    lastResult: null,
    error: '',
    agentTab: 'agent',
  }

  const escapeHtml = (value = '') => String(value)
    .replaceAll('&', '&amp;').replaceAll('<', '&lt;').replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;').replaceAll("'", '&#039;')

  const safeJson = (value) => {
    try { return JSON.stringify(value, null, 2) } catch { return String(value) }
  }

  const api = async (path, options) => {
    const response = await fetch(path, options)
    if (!response.ok) throw new Error((await response.text()) || `${response.status} ${response.statusText}`)
    return response.json()
  }

  const toast = (message) => {
    const node = $('#toast')
    node.textContent = message
    node.hidden = false
    clearTimeout(toast.timer)
    toast.timer = setTimeout(() => { node.hidden = true }, 2800)
  }

  const languageFor = (path) => {
    const ext = path.split('.').pop()?.toLowerCase() || ''
    return ({ py: 'python', ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript', json: 'json', md: 'markdown', yaml: 'yaml', yml: 'yaml', sh: 'bash', css: 'css', html: 'markup' })[ext] || 'plaintext'
  }

  const iconFor = (name) => {
    if (/\.py$/.test(name)) return '<span class="file-glyph python">PY</span>'
    if (/\.(ts|tsx|js|jsx)$/.test(name)) return '<span class="file-glyph js">JS</span>'
    if (/\.json$/.test(name)) return '<span class="file-glyph json">{ }</span>'
    if (/\.(ya?ml|toml)$/.test(name)) return '<span class="file-glyph yaml">Y</span>'
    if (/\.md$/.test(name)) return '<span class="file-glyph md">M↓</span>'
    return '<span class="file-glyph">·</span>'
  }

  async function loadMeta() {
    if (OFFLINE) {
      seedOfflineDemo()
      renderChrome(); renderLeft(); renderInspect(); renderEditor()
      return
    }
    const calls = await Promise.allSettled([
      api('/api/health'), api('/api/workspace/tree'), api('/api/sessions'), api('/api/tasks'), api('/api/worktrees'), api('/api/workflows')
    ])
    if (calls[0].status === 'fulfilled') state.health = calls[0].value
    if (calls[1].status === 'fulfilled') state.tree = calls[1].value.items || []
    if (calls[2].status === 'fulfilled') state.sessions = calls[2].value.items || []
    if (calls[3].status === 'fulfilled') state.tasks = calls[3].value.items || []
    if (calls[4].status === 'fulfilled') state.worktrees = calls[4].value.items || []
    if (calls[5].status === 'fulfilled') state.workflows = calls[5].value.items || []
    renderChrome()
    renderLeft()
    renderInspect()
    if (!state.activePath && state.tree.length) openFile('src/codeagent/runtime.py')
  }


  function seedOfflineDemo() {
    if (state.health) return
    state.health = { status:'ok', workspaceName:'codeagent-harness', model:'Demo Runtime', provider:'demo', demo:true, branch:'portfolio/web-ide', metrics:{ modules:33, tests:7, tools:30, lines:3234 } }
    state.model = 'Demo Runtime'; state.demo = true; state.connected = true; state.sessionId = 'demo_20260910';
    state.tools = ['bash','read_file','write_file','edit_file','glob','grep','todo_write','memory_search','task_create','task_list','spawn_subagent','team_run','worktree_create','connect_mcp','workflow_run','cron_add']
    state.tree = [
      {name:'src',path:'src',type:'directory',children:[{name:'codeagent',path:'src/codeagent',type:'directory',children:[
        {name:'runtime.py',path:'src/codeagent/runtime.py',type:'file'},{name:'events.py',path:'src/codeagent/events.py',type:'file'},{name:'permission.py',path:'src/codeagent/permission.py',type:'file'},{name:'workflow.py',path:'src/codeagent/workflow.py',type:'file'},{name:'goal.py',path:'src/codeagent/goal.py',type:'file'}]}]},
      {name:'tests',path:'tests',type:'directory',children:[{name:'test_agent_loop.py',path:'tests/test_agent_loop.py',type:'file'},{name:'test_workflow.py',path:'tests/test_workflow.py',type:'file'}]},
      {name:'web',path:'web',type:'directory',children:[{name:'src',path:'web/src',type:'directory',children:[{name:'app.js',path:'web/src/app.js',type:'file'},{name:'styles.css',path:'web/src/styles.css',type:'file'}]}]},
      {name:'README.md',path:'README.md',type:'file'},{name:'pyproject.toml',path:'pyproject.toml',type:'file'}
    ]
    state.sessions = [{id:'demo-a',title:'Trace the runtime architecture',status:'completed',inputTokens:1917,outputTokens:278},{id:'demo-b',title:'Review permission boundaries',status:'completed',inputTokens:1238,outputTokens:201}]
    state.tasks = [{id:'t1',subject:'Web IDE execution trace',status:'completed',owner:'agent'},{id:'t2',subject:'Provider token streaming',status:'pending',owner:null}]
    state.worktrees = [{branch:'refs/heads/portfolio/web-ide',worktree:'~/codeagent/.worktrees/web-ide'}]
    state.workflows = [{name:'code_review',path:'examples/code_review.yaml'}]
    if (!state.openFiles.length) {
      const content = `class AgentRuntime:
    """One agent loop, surrounded by composable harness mechanisms."""

    async def run(self, prompt: str) -> RunResult:
        await self.events.emit("user_prompt", prompt=prompt)
        self.messages.append({"role": "user", "content": prompt})

        for iteration in range(1, self.settings.max_iterations + 1):
            prepared = self.context.prepare(self.messages)
            await self.events.emit("model_start", iteration=iteration)
            turn = await self.provider.complete(
                messages=prepared,
                system=self.system_prompt(prompt),
                tools=self.tools.schemas(),
                max_tokens=self.settings.max_tokens,
            )

            if turn.tool_calls:
                results = []
                for call in turn.tool_calls:
                    result = await self._execute_call(call)
                    results.append(result.as_block())
                self.messages.append({"role": "user", "content": results})
                continue

            action, reason = await self.goal.on_proposed_stop(self.messages)
            if action == "block":
                self.messages.append({"role": "user", "content": reason})
                continue

            await self.events.emit("final", text=turn.text)
            return RunResult(turn.text, self.messages)
`
      state.openFiles = [{path:'src/codeagent/runtime.py',content,savedContent:content}]; state.activePath = 'src/codeagent/runtime.py'
    }
  }

  function renderChrome() {
    const h = state.health
    if (h) {
      $('#repo-name').textContent = h.workspaceName
      $('#branch-chip').textContent = `⑂ ${h.branch}`
      $('#status-branch').textContent = `⑂ ${h.branch}`
      $('#model-name').textContent = state.model || h.model
      $('#provider-status').textContent = h.provider
      $('#tool-status').textContent = `${state.tools.length || h.metrics?.tools || 0} tools`
    }
    const conn = $('#connection-chip')
    conn.classList.toggle('online', state.connected)
    $('span', conn).textContent = state.connected ? 'runtime online' : 'offline'
    $('#socket-status').textContent = state.connected ? 'WebSocket' : 'disconnected'
    $('#runtime-status').textContent = state.running ? '● agent running' : (state.connected ? '● agent ready' : '● offline')
    $('#agent-state-label').textContent = state.running ? 'Working' : (state.connected ? 'Ready' : 'Offline')
    $('#run-top').classList.toggle('stop', state.running)
    $('#run-top span').textContent = state.running ? 'Stop' : 'Run'
    $('#run-top').firstChild.textContent = state.running ? '■ ' : '▶ '
  }

  function renderLeft() {
    $('#left-title').textContent = state.leftView[0].toUpperCase() + state.leftView.slice(1)
    $('#left-new').hidden = state.leftView !== 'sessions'
    $$('.rail-button[data-view]').forEach((btn) => btn.classList.toggle('active', btn.dataset.view === state.leftView && state.leftOpen))
    const root = $('#left-content')
    if (!state.leftOpen) return

    if (state.leftView === 'explorer') {
      root.innerHTML = `<div class="section-heading">⌄ <span>${escapeHtml((state.health?.workspaceName || 'WORKSPACE').toUpperCase())}</span></div><div class="file-tree">${treeHtml(state.tree, 0)}</div>`
      $$('.tree-row', root).forEach((row) => row.addEventListener('click', () => {
        const path = row.dataset.path
        if (row.dataset.type === 'directory') {
          state.expanded.has(path) ? state.expanded.delete(path) : state.expanded.add(path)
          renderLeft()
        } else openFile(path)
      }))
      return
    }

    if (state.leftView === 'sessions') {
      root.innerHTML = `<div class="mini-search">⌕<input id="session-filter" placeholder="Filter sessions"></div><div id="object-list" class="object-list">${sessionListHtml(state.sessions)}</div>`
      $('#session-filter').addEventListener('input', (e) => {
        const value = e.target.value.toLowerCase()
        $('#object-list').innerHTML = sessionListHtml(state.sessions.filter((s) => s.title.toLowerCase().includes(value)))
        bindSessionRows()
      })
      bindSessionRows()
      return
    }

    if (state.leftView === 'tasks') {
      root.innerHTML = `<div class="object-list">${state.tasks.length ? state.tasks.map((task, i) => `<div class="object-row static"><span class="task-state" data-status="${escapeHtml(task.status || 'pending')}"></span><div class="object-row-body"><strong>${escapeHtml(task.subject || task.title || `Task ${i + 1}`)}</strong><span>${escapeHtml(task.status || 'pending')}${task.owner ? ` · ${escapeHtml(task.owner)}` : ''}</span></div></div>`).join('') : emptyMini('Task graph is empty')}</div>`
      return
    }

    if (state.leftView === 'worktrees') {
      root.innerHTML = `<div class="object-list">${state.worktrees.length ? state.worktrees.map((item, i) => `<div class="object-row static"><span class="object-row-icon">⑂</span><div class="object-row-body"><strong>${escapeHtml((item.branch || `worktree-${i + 1}`).replace('refs/heads/', ''))}</strong><span title="${escapeHtml(item.worktree || '')}">${escapeHtml(item.worktree || '')}</span></div></div>`).join('') : emptyMini('No Git worktrees found')}</div>`
      return
    }

    root.innerHTML = `<div class="object-list">${state.workflows.length ? state.workflows.map((item) => `<button class="object-row workflow-row" data-path="${escapeHtml(item.path)}"><span class="object-row-icon">◇</span><div class="object-row-body"><strong>${escapeHtml(item.name)}</strong><span>${escapeHtml(item.path)}</span></div></button>`).join('') : emptyMini('No workflow YAML files')}</div>`
    $$('.workflow-row', root).forEach((row) => row.addEventListener('click', () => openFile(row.dataset.path)))
  }

  function treeHtml(nodes, depth) {
    return nodes.map((node) => {
      const folder = node.type === 'directory'
      const open = folder && state.expanded.has(node.path)
      const selected = node.path === state.activePath
      return `<div class="tree-node"><button class="tree-row ${selected ? 'selected' : ''}" style="padding-left:${8 + depth * 12}px" data-path="${escapeHtml(node.path)}" data-type="${node.type}"><span class="tree-caret">${folder ? (open ? '⌄' : '›') : ''}</span><span class="tree-icon">${folder ? (open ? '▾' : '▸') : iconFor(node.name)}</span><span class="tree-name">${escapeHtml(node.name)}</span></button>${folder && open ? treeHtml(node.children || [], depth + 1) : ''}</div>`
    }).join('')
  }

  function sessionListHtml(items) {
    return items.length ? items.map((s) => `<button class="object-row session-row" data-id="${escapeHtml(s.id)}"><span class="object-row-icon">◎</span><div class="object-row-body"><strong>${escapeHtml(s.title)}</strong><span>${escapeHtml(s.status)} · ${Number((s.inputTokens || 0) + (s.outputTokens || 0)).toLocaleString()} tokens</span></div></button>`).join('') : emptyMini('No saved sessions yet')
  }

  function bindSessionRows() {
    $$('.session-row').forEach((row) => row.addEventListener('click', () => sendSocket({ type: 'resume_session', sessionId: row.dataset.id })))
  }

  function emptyMini(label) { return `<div class="empty-mini">${escapeHtml(label)}</div>` }

  async function openFile(path) {
    if (!path) return
    if (OFFLINE) {
      const existing = state.openFiles.find((f) => f.path === path)
      if (existing) { state.activePath = path; state.reviewMode = false; renderEditor(); renderLeft(); return }
      const content = `# ${path}\n\n# Offline portfolio preview\n# Run codeagent-web for live workspace content.\n`
      state.openFiles.push({path, content, savedContent:content}); state.activePath = path; renderEditor(); renderLeft(); return
    }
    state.leftView = 'explorer'
    state.reviewMode = false
    state.diff = null
    const existing = state.openFiles.find((f) => f.path === path)
    if (existing) {
      state.activePath = path
      renderEditor()
      renderLeft()
      return
    }
    try {
      const payload = await api(`/api/workspace/file?path=${encodeURIComponent(path)}`)
      state.openFiles.push({ path: payload.path, content: payload.content, savedContent: payload.content })
      state.activePath = payload.path
      renderEditor()
      renderLeft()
    } catch (error) { toast(error.message || String(error)) }
  }

  function renderEditor() {
    const active = state.openFiles.find((f) => f.path === state.activePath)
    const tabs = $('#editor-tabs')
    tabs.innerHTML = state.openFiles.length ? state.openFiles.map((file) => {
      const name = file.path.split('/').pop()
      const dirty = file.content !== file.savedContent
      return `<button class="editor-tab ${file.path === state.activePath ? 'active' : ''}" data-path="${escapeHtml(file.path)}"><span class="tab-file-icon">${iconFor(file.path)}</span><span>${escapeHtml(name)}</span>${dirty ? '<i class="dirty-dot"></i>' : '<i class="tab-close">×</i>'}</button>`
    }).join('') : '<span class="tab-placeholder">No file open</span>'
    $$('.editor-tab', tabs).forEach((tab) => tab.addEventListener('click', (event) => {
      if (event.target.classList.contains('tab-close')) { closeFile(tab.dataset.path); return }
      state.activePath = tab.dataset.path
      state.reviewMode = false
      renderEditor()
      renderLeft()
    }))

    $('#editor-empty').hidden = Boolean(active)
    $('#code-editor').hidden = !active || state.reviewMode
    $('#diff-view').hidden = !active || !state.reviewMode
    $('#dirty-label').hidden = !active || active.content === active.savedContent
    $('#save-file').disabled = !active || active.content === active.savedContent
    $('#editor-file-label').textContent = active?.path || 'No file'
    $('#editor-language').textContent = languageFor(active?.path || '')
    $('#breadcrumbs').innerHTML = active ? active.path.split('/').map((part, i, arr) => `<span>${escapeHtml(part)}${i < arr.length - 1 ? '<i>›</i>' : ''}</span>`).join('') : ''
    $('#buffer-status').textContent = active && active.content !== active.savedContent ? '● unsaved' : '✓ clean buffer'
    $('#review-diff').classList.toggle('active', state.reviewMode)

    if (active && !state.reviewMode) {
      const input = $('#code-input')
      if (input.value !== active.content) input.value = active.content
      updateHighlight()
    }
    if (active && state.reviewMode && state.diff) renderDiff()
  }

  function closeFile(path) {
    const index = state.openFiles.findIndex((f) => f.path === path)
    state.openFiles.splice(index, 1)
    if (state.activePath === path) state.activePath = state.openFiles[Math.max(0, index - 1)]?.path || state.openFiles[0]?.path || ''
    state.reviewMode = false
    renderEditor(); renderLeft()
  }

  function updateHighlight() {
    const active = state.openFiles.find((f) => f.path === state.activePath)
    if (!active) return
    const input = $('#code-input')
    const code = $('#highlight-code')
    const lang = languageFor(active.path)
    const grammar = window.Prism?.languages?.[lang] || window.Prism?.languages?.plaintext
    code.className = `language-${lang}`
    code.innerHTML = grammar && window.Prism ? window.Prism.highlight(input.value + '\n', grammar, lang) : escapeHtml(input.value + '\n')
    const lines = Math.max(1, input.value.split('\n').length)
    $('#line-gutter').innerHTML = Array.from({ length: lines }, (_, i) => `<span>${i + 1}</span>`).join('')
  }

  function syncEditorScroll() {
    const input = $('#code-input')
    $('#highlight-layer').scrollTop = input.scrollTop
    $('#highlight-layer').scrollLeft = input.scrollLeft
    $('#line-gutter').scrollTop = input.scrollTop
  }

  async function saveActive() {
    const active = state.openFiles.find((f) => f.path === state.activePath)
    if (!active || active.content === active.savedContent) return
    try {
      await api('/api/workspace/file', { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ path: active.path, content: active.content }) })
      active.savedContent = active.content
      renderEditor(); loadMeta(); toast(`Saved ${active.path}`)
    } catch (error) { toast(error.message || String(error)) }
  }

  async function toggleReview() {
    if (!state.activePath) return
    if (state.reviewMode) { state.reviewMode = false; renderEditor(); return }
    try {
      state.diff = await api(`/api/git/file-diff?path=${encodeURIComponent(state.activePath)}`)
      state.reviewMode = true
      renderEditor()
    } catch (error) { toast(error.message || String(error)) }
  }

  function renderDiff() {
    const active = state.openFiles.find((f) => f.path === state.activePath)
    if (!active || !state.diff) return
    $('#diff-original').innerHTML = diffLines(state.diff.original || '', active.content || '')
    $('#diff-modified').innerHTML = diffLines(active.content || '', state.diff.original || '')
  }

  function diffLines(primary, other) {
    const a = primary.split('\n'), b = other.split('\n')
    return a.map((line, i) => `<span class="${line === b[i] ? '' : 'changed'}"><i>${i + 1}</i>${escapeHtml(line) || ' '}</span>`).join('')
  }

  function connectAgent() {
    if (OFFLINE) { state.connected = true; state.demo = true; renderChrome(); renderInspect(); return }
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
    const ws = new WebSocket(`${protocol}//${location.host}/ws/agent`)
    state.ws = ws
    ws.onopen = () => { state.connected = true; renderChrome() }
    ws.onclose = () => { state.connected = false; state.running = false; renderChrome(); setTimeout(connectAgent, 1800) }
    ws.onerror = () => { state.error = 'Agent socket connection failed.'; renderAgent() }
    ws.onmessage = (event) => handleSocket(JSON.parse(event.data))
  }

  function sendSocket(payload) {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return false
    state.ws.send(JSON.stringify(payload)); return true
  }

  function handleSocket(payload) {
    if (payload.type === 'ready') {
      state.sessionId = payload.sessionId; state.model = payload.model; state.demo = payload.demo; state.tools = payload.tools || []; state.connected = true
      renderChrome(); renderInspect(); return
    }
    if (payload.type === 'agent_event') {
      state.events.push(payload.event); if (state.events.length > 500) state.events.shift()
      renderAgent(); renderTrace(); renderInspect(); renderChrome(); return
    }
    if (payload.type === 'permission_request') { state.permission = payload; renderPermission(); return }
    if (payload.type === 'run_complete') { state.lastResult = payload.result; state.running = false; renderAgent(); renderChrome(); loadMeta(); return }
    if (payload.type === 'run_cancelled') { state.running = false; renderAgent(); renderChrome(); return }
    if (payload.type === 'session_changed') { state.sessionId = payload.sessionId; state.events = []; state.lastResult = null; state.error = ''; renderAgent(); renderTrace(); renderInspect(); loadMeta(); return }
    if (payload.type === 'error') { state.error = payload.message; state.running = false; renderAgent(); renderChrome() }
  }

  function submitAgent(prompt, goal = '') {
    const value = String(prompt || '').trim()
    if (!value || state.running || !state.connected) return
    if (OFFLINE) { simulateOfflineRun(value); return }
    if (!sendSocket({ type: 'prompt', prompt: value, goal: goal || undefined })) return
    state.running = true; state.error = ''; state.lastResult = null; renderAgent(); renderChrome()
  }

  function simulateOfflineRun(prompt) {
    state.running = true; state.events = [{type:'user_prompt',data:{prompt},timestamp:Date.now()/1000}]; renderAgent(); renderChrome()
    const push = (delay,event) => setTimeout(() => { state.events.push({...event,timestamp:Date.now()/1000}); renderAgent(); renderTrace(); renderChrome() }, delay)
    push(350,{type:'model_start',data:{iteration:1}})
    push(700,{type:'model_end',data:{iteration:1,text:'I’ll trace the runtime boundary first, then verify how tools enter the loop.',tool_count:1,input_tokens:364,output_tokens:71}})
    push(1050,{type:'tool_requested',data:{name:'read_file',arguments:{path:'src/codeagent/runtime.py',limit:70}}})
    push(1350,{type:'permission',data:{name:'read_file',action:'allow',reason:'safe workspace read'}})
    push(1650,{type:'tool_end',data:{name:'read_file',output:'AgentRuntime centralizes context, model calls, permissions, hooks and tool dispatch.',is_error:false}})
    setTimeout(() => { state.events.push({type:'model_end',data:{iteration:2,text:'The runtime has a strong portfolio boundary: one stable loop owns execution while EventBus exposes observability. The next highest-value improvement is provider token streaming.',tool_count:0,input_tokens:941,output_tokens:128},timestamp:Date.now()/1000}); state.events.push({type:'final',data:{text:'done'},timestamp:Date.now()/1000}); state.lastResult={status:'completed',inputTokens:1305,outputTokens:199}; state.running=false; renderAgent(); renderTrace(); renderChrome() },2200)
  }

  function renderAgent() {
    const root = $('#agent-view')
    $('#trace-count').textContent = state.events.filter((e) => !['user_prompt', 'final'].includes(e.type)).length
    if (!state.events.length && !state.lastResult) {
      root.innerHTML = `<div class="agent-empty-state"><div class="empty-orbit">⌘</div><h3>Runtime is observable by default.</h3><p>Ask the agent to inspect, edit, test, or review the repository. Tool calls, permission gates, context changes, and goal decisions stay visible here.</p><div class="capability-grid"><span>⌕ inspect code</span><span>▣ run checks</span><span>⑂ isolate worktrees</span><span>◎ verify goals</span></div><button id="demo-run" class="demo-run">↗ Run architecture demo</button></div>`
      $('#demo-run').addEventListener('click', () => submitAgent('Inspect this repository and explain the coding-agent runtime architecture. Verify your claims with tools, then identify the highest-value next improvement.'))
      return
    }
    const chunks = []
    const branch = state.health?.branch || 'local'
    const mode = state.demo || state.health?.demo ? 'sandbox' : 'live'
    chunks.push(`<div class="run-context-strip"><span><b></b>${escapeHtml(mode)}</span><span>${escapeHtml(branch)}</span><span>${state.tools.length} tools</span><span class="mono">${escapeHtml((state.sessionId || 'session').slice(-8))}</span></div>`)
    for (const event of state.events) {
      if (event.type === 'user_prompt') {
        chunks.push(`<div class="conversation-turn user-turn"><div class="turn-label"><span>You</span><time>${time(event.timestamp)}</time></div><p>${escapeHtml(event.data.prompt || '')}</p></div>`)
      }
      if (event.type === 'model_end' && event.data.text) {
        chunks.push(`<div class="conversation-turn assistant-turn"><div class="turn-label"><span>⌁ CodeAgent</span><time>${time(event.timestamp)}</time></div><p>${escapeHtml(event.data.text)}</p>${Number(event.data.tool_count || 0) ? `<div class="turn-foot">⌘ ${event.data.tool_count} tool call${Number(event.data.tool_count) === 1 ? '' : 's'}</div>` : ''}</div>`)
      }
    }
    if (state.running) chunks.push('<div class="agent-running-row"><span class="spinner">◌</span><span>Agent is working</span><i></i><i></i><i></i></div>')
    if (state.lastResult && !state.running) chunks.push(`<div class="run-summary"><div class="run-summary-title">✓ Run ${escapeHtml(state.lastResult.status)}</div><div class="run-summary-metrics"><span>${Number(state.lastResult.inputTokens || 0).toLocaleString()} input</span><span>${Number(state.lastResult.outputTokens || 0).toLocaleString()} output</span></div></div>`)
    if (state.error) chunks.push(`<div class="agent-error">× ${escapeHtml(state.error)}</div>`)
    root.innerHTML = `<div class="agent-conversation">${chunks.join('')}</div>`
    requestAnimationFrame(() => { const sc = $('#agent-scroll'); sc.scrollTop = sc.scrollHeight })
  }

  function renderTrace() {
    const trace = state.events.filter((e) => !['user_prompt', 'final'].includes(e.type))
    $('#trace-count').textContent = trace.length
    const toolRuns = trace.filter((e) => e.type === 'tool_end').length
    const modelTurns = trace.filter((e) => e.type === 'model_end').length
    const gates = trace.filter((e) => e.type === 'permission').length
    $('#trace-view').innerHTML = `<div class="trace-overview"><span><b>${trace.length}</b> events</span><span><b>${modelTurns}</b> turns</span><span><b>${toolRuns}</b> tools</span><span><b>${gates}</b> gates</span></div><div class="trace-list">${trace.length ? trace.map((e) => `<div class="trace-item ${e.type}"><div class="trace-rail"><span>${traceIcon(e.type)}</span><i></i></div><div class="trace-copy"><div class="trace-title"><strong>${escapeHtml(eventTitle(e))}</strong><time>${time(e.timestamp, true)}</time></div>${eventDetail(e) ? `<pre>${escapeHtml(eventDetail(e))}</pre>` : ''}</div></div>`).join('') : '<div class="trace-empty">Execution events will appear here.</div>'}</div>`
  }

  function traceIcon(type) {
    if (type.startsWith('tool_')) return '⌘'
    if (type.startsWith('permission')) return '◇'
    if (type.startsWith('context')) return '◫'
    if (type.startsWith('goal')) return '◎'
    if (type.startsWith('model')) return '⌁'
    if (type.startsWith('background')) return '▣'
    return '·'
  }

  function eventTitle(e) {
    const d = e.data || {}
    if (e.type === 'tool_requested') return `Requested ${d.name}`
    if (e.type === 'tool_start') return `Running ${d.name}`
    if (e.type === 'tool_end') return `${d.name} ${d.is_error ? 'failed' : 'completed'}`
    if (e.type === 'permission') return `${d.name} · ${d.action}`
    if (e.type === 'model_start') return `Model turn ${d.iteration}`
    if (e.type === 'model_end') return `${d.tool_count || 0} tool call${Number(d.tool_count) === 1 ? '' : 's'}`
    if (e.type === 'context_compacted') return 'Context compacted'
    if (e.type === 'goal_decision') return `Goal · ${d.action}`
    return e.type.replaceAll('_', ' ')
  }

  function eventDetail(e) {
    const d = e.data || {}
    if (['tool_requested', 'tool_start'].includes(e.type)) return safeJson(d.arguments).slice(0, 360)
    if (e.type === 'tool_end') return String(d.output || '').slice(0, 360)
    if (e.type === 'permission' || e.type === 'goal_decision') return String(d.reason || '')
    if (e.type === 'model_end') return `${Number(d.input_tokens || 0).toLocaleString()} in · ${Number(d.output_tokens || 0).toLocaleString()} out`
    if (e.type === 'context_compacted') return `${Number(d.before_chars || 0).toLocaleString()} → ${Number(d.after_chars || 0).toLocaleString()} chars`
    return ''
  }

  function renderInspect() {
    const h = state.health
    const latestModel = [...state.events].reverse().find((e) => e.type === 'model_end')
    const contextTokens = Number(latestModel?.data?.input_tokens || 0)
    const currentGoal = state.events.findLast?.((e) => e.type === 'goal_decision')
    $('#inspect-view').innerHTML = `<div class="inspect-panel">
      <section class="runtime-map-section">
        <h4>Execution topology <span>live</span></h4>
        <div class="runtime-map">
          <div class="runtime-node primary"><small>01</small><strong>Model</strong><span>${escapeHtml(state.model || h?.model || 'provider')}</span></div>
          <i>→</i>
          <div class="runtime-node"><small>02</small><strong>Gate</strong><span>permission + hooks</span></div>
          <i>→</i>
          <div class="runtime-node"><small>03</small><strong>Tools</strong><span>${state.tools.length || h?.metrics?.tools || 0} registered</span></div>
        </div>
        <div class="runtime-return"><span></span><b>tool_result returns to the same agent loop</b></div>
      </section>
      <section><h4>Runtime</h4><dl><div><dt>Connection</dt><dd class="${state.connected ? 'good' : 'bad'}">${state.connected ? 'Online' : 'Offline'}</dd></div><div><dt>Mode</dt><dd>${state.demo || h?.demo ? 'Deterministic demo' : 'Live provider'}</dd></div><div><dt>Context</dt><dd>${contextTokens.toLocaleString()} tokens</dd></div><div><dt>Session</dt><dd class="mono truncate">${escapeHtml(state.sessionId || 'pending')}</dd></div></dl></section>
      <section><h4>Repository <span>workspace</span></h4><div class="metric-strip"><div><strong>${h?.metrics?.modules ?? 0}</strong><span>modules</span></div><div><strong>${h?.metrics?.tests ?? 0}</strong><span>tests</span></div><div><strong>${h?.metrics?.lines?.toLocaleString?.() ?? 0}</strong><span>lines</span></div></div></section>
      <section><h4>Execution state</h4><div class="signal-list"><div><span class="signal-dot ${state.running ? 'busy' : 'ok'}"></span><b>${state.running ? 'Agent executing' : 'Agent idle'}</b><small>${state.events.length} events</small></div><div><span class="signal-dot"></span><b>Permission gate</b><small>host controlled</small></div><div><span class="signal-dot"></span><b>Completion goal</b><small>${currentGoal ? escapeHtml(currentGoal.data?.action || 'evaluated') : 'optional'}</small></div></div></section>
      <section><h4>Tool surface <span>${state.tools.length}</span></h4><div class="tool-cloud">${state.tools.map((tool) => `<span>${escapeHtml(tool)}</span>`).join('')}</div></section>
    </div>`
  }

  function renderPermission() {
    const slot = $('#permission-slot')
    if (!state.permission) { slot.innerHTML = ''; return }
    slot.innerHTML = `<div class="permission-card"><div class="permission-title"><span>◇</span><div><strong>Approval required</strong><span>${escapeHtml(state.permission.reason)}</span></div></div><pre>${escapeHtml(state.permission.tool)}(${escapeHtml(safeJson(state.permission.arguments))})</pre><div class="permission-actions"><button id="deny-permission">Deny</button><button id="allow-permission" class="allow">Allow once</button></div></div>`
    $('#deny-permission').addEventListener('click', () => answerPermission(false))
    $('#allow-permission').addEventListener('click', () => answerPermission(true))
  }

  function answerPermission(allow) {
    if (!state.permission) return
    sendSocket({ type: 'permission_response', id: state.permission.id, allow })
    state.permission = null; renderPermission()
  }

  function time(ts, seconds = false) {
    return new Date(ts * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', ...(seconds ? { second: '2-digit' } : {}) })
  }

  async function runTerminal(command) {
    const value = command.trim(); if (!value) return
    const form = $('#terminal-form')
    form.insertAdjacentHTML('beforebegin', `<div class="command-line">❯ ${escapeHtml(value)}</div>`)
    $('#terminal-input').value = ''; $('#terminal-input').disabled = true; $('#terminal-running').textContent = 'running'
    try {
      const result = await api('/api/terminal', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command: value }) })
      const output = String(result.output || '').trimEnd()
      if (output) form.insertAdjacentHTML('beforebegin', output.split('\n').map((line) => `<div>${escapeHtml(line) || '&nbsp;'}</div>`).join(''))
      else form.insertAdjacentHTML('beforebegin', `<div class="terminal-muted">[exit ${result.code}]</div>`)
    } catch (error) { form.insertAdjacentHTML('beforebegin', `<div class="terminal-error">error: ${escapeHtml(error.message || String(error))}</div>`) }
    finally {
      $('#terminal-input').disabled = false; $('#terminal-running').textContent = ''; $('#terminal-input').focus()
      const body = $('#terminal-body'); body.scrollTop = body.scrollHeight
    }
  }

  function setTerminal(open) {
    state.terminalOpen = open
    $('#terminal-panel').hidden = !open
    $('#center-stack').classList.toggle('terminal-open', open)
    $('#toggle-terminal-top').classList.toggle('active', open)
  }

  function flattenTree(nodes) { return nodes.flatMap((n) => n.type === 'file' ? [n] : flattenTree(n.children || [])) }

  function openPalette() {
    $('#palette-backdrop').hidden = false
    $('#palette-input').value = ''
    renderPalette('')
    setTimeout(() => $('#palette-input').focus(), 0)
  }
  function closePalette() { $('#palette-backdrop').hidden = true }
  function renderPalette(query) {
    const q = query.trim().toLowerCase()
    const files = flattenTree(state.tree)
    const suggested = q ? files.filter((f) => f.path.toLowerCase().includes(q)).slice(0, 9) : files.filter((f) => /(runtime|events|permission|workflow)\.py$/.test(f.path)).slice(0, 6)
    const actions = [
      { id: 'terminal', label: 'Toggle terminal', shortcut: '⌘ J' },
      { id: 'review', label: 'Review current file diff', shortcut: '⌥ D' },
      { id: 'refresh', label: 'Refresh workspace', shortcut: '' },
      { id: 'session', label: 'New agent session', shortcut: '' },
    ].filter((a) => !q || a.label.toLowerCase().includes(q))
    $('#palette-content').innerHTML = `${actions.length ? `<div class="palette-group"><label>Actions</label>${actions.map((a) => `<button data-action="${a.id}"><span><b>⌘</b>${a.label}</span>${a.shortcut ? `<kbd>${a.shortcut}</kbd>` : ''}</button>`).join('')}</div>` : ''}${suggested.length ? `<div class="palette-group"><label>Files</label>${suggested.map((f) => `<button data-file="${escapeHtml(f.path)}"><span><b>${iconFor(f.name)}</b>${escapeHtml(f.path)}</span></button>`).join('')}</div>` : ''}`
    $$('[data-action]', $('#palette-content')).forEach((btn) => btn.addEventListener('click', () => {
      if (btn.dataset.action === 'terminal') setTerminal(!state.terminalOpen)
      if (btn.dataset.action === 'review') toggleReview()
      if (btn.dataset.action === 'refresh') loadMeta()
      if (btn.dataset.action === 'session') sendSocket({ type: 'new_session' })
      closePalette()
    }))
    $$('[data-file]', $('#palette-content')).forEach((btn) => btn.addEventListener('click', () => { openFile(btn.dataset.file); closePalette() }))
  }

  function bindEvents() {
    $$('.rail-button[data-view]').forEach((btn) => btn.addEventListener('click', () => {
      const view = btn.dataset.view
      if (state.leftView === view && state.leftOpen) state.leftOpen = false
      else { state.leftView = view; state.leftOpen = true }
      $('#left-pane-wrap').classList.toggle('open', state.leftOpen)
      $('#left-pane-wrap').classList.toggle('closed', !state.leftOpen)
      $('#workspace-grid').classList.toggle('left-closed', !state.leftOpen)
      renderLeft()
    }))
    $('#left-refresh').addEventListener('click', loadMeta)
    $('#left-new').addEventListener('click', () => sendSocket({ type: 'new_session' }))
    $('#new-session').addEventListener('click', () => sendSocket({ type: 'new_session' }))
    $('#toggle-terminal-top').addEventListener('click', () => setTerminal(!state.terminalOpen))
    $('#terminal-close').addEventListener('click', () => setTerminal(false))
    $('#terminal-clear').addEventListener('click', () => {
      const form = $('#terminal-form'); [...$('#terminal-body').children].filter((el) => el !== form).forEach((el) => el.remove())
    })
    $('#terminal-form').addEventListener('submit', (e) => { e.preventDefault(); runTerminal($('#terminal-input').value) })
    $('#save-file').addEventListener('click', saveActive)
    $('#review-diff').addEventListener('click', toggleReview)
    $('#code-input').addEventListener('input', (e) => {
      const active = state.openFiles.find((f) => f.path === state.activePath); if (!active) return
      active.content = e.target.value; updateHighlight(); renderEditor()
    })
    $('#code-input').addEventListener('scroll', syncEditorScroll)
    $('#code-input').addEventListener('keydown', (e) => {
      if (e.key === 'Tab') {
        e.preventDefault(); const input = e.target; const start = input.selectionStart, end = input.selectionEnd
        input.setRangeText('    ', start, end, 'end'); input.dispatchEvent(new Event('input', { bubbles: true }))
      }
    })
    $('#agent-form').addEventListener('submit', (e) => {
      e.preventDefault(); const input = $('#agent-input'); submitAgent(input.value, $('#goal-input').value.trim()); input.value = ''
    })
    $('#agent-input').addEventListener('keydown', (e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); $('#agent-form').requestSubmit() } })
    $('#goal-toggle').addEventListener('click', () => { $('#goal-field').hidden = !$('#goal-field').hidden; if (!$('#goal-field').hidden) $('#goal-input').focus() })
    $('#goal-close').addEventListener('click', () => { $('#goal-field').hidden = true; $('#goal-input').value = '' })
    $$('.agent-tabs button').forEach((btn) => btn.addEventListener('click', () => {
      state.agentTab = btn.dataset.agentTab
      $$('.agent-tabs button').forEach((item) => item.classList.toggle('active', item === btn))
      $('#agent-view').hidden = state.agentTab !== 'agent'; $('#trace-view').hidden = state.agentTab !== 'trace'; $('#inspect-view').hidden = state.agentTab !== 'inspect'
    }))
    $('#run-top').addEventListener('click', () => {
      if (state.running) { sendSocket({ type: 'cancel' }); return }
      submitAgent(`Inspect ${state.activePath || 'this repository'} and explain the most important implementation detail. Use tools to verify your answer.`)
    })
    $('#command-trigger').addEventListener('click', openPalette)
    $('#palette-backdrop').addEventListener('mousedown', (e) => { if (e.target === e.currentTarget) closePalette() })
    $('#palette-input').addEventListener('input', (e) => renderPalette(e.target.value))
    $('#palette-input').addEventListener('keydown', (e) => { if (e.key === 'Escape') closePalette() })
    window.addEventListener('keydown', (e) => {
      const mod = e.metaKey || e.ctrlKey
      if (mod && e.key.toLowerCase() === 'k') { e.preventDefault(); openPalette() }
      if (mod && e.key.toLowerCase() === 'j') { e.preventDefault(); setTerminal(!state.terminalOpen) }
      if (mod && e.key.toLowerCase() === 's') { e.preventDefault(); saveActive() }
      if (e.altKey && e.key.toLowerCase() === 'd') { e.preventDefault(); toggleReview() }
      if (e.key === 'Escape' && !$('#palette-backdrop').hidden) closePalette()
    })
  }

  bindEvents()
  renderAgent(); renderTrace(); renderInspect(); setTerminal(true); renderChrome(); loadMeta(); connectAgent()
})()
