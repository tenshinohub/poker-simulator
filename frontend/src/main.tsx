import React, { useEffect, useMemo, useState } from 'react'
import { createRoot } from 'react-dom/client'
import './style.css'

type Player = { player_id: string; name: string; seat: number; position?: string; is_button?: boolean; stack: number; street_bet: number; folded: boolean; all_in: boolean; is_human: boolean; action_status?: string; last_action?: string | null }
type EventData = {
  type: string; session_id?: string; hand_id?: string; street?: string; human_player_id?: string;
  hole_cards?: string[]; board?: string[]; players?: Player[]; pot?: number; current_bet?: number; to_call?: number;
  button_seat?: number; human_position?: string;
  legal_actions?: Record<string, boolean | number | null>; winners?: string[]; winner_names?: string[]; payouts?: Record<string, number>;
  ending_stacks?: Record<string, number>; revealed_hole_cards?: Record<string, string[]>; reason?: string; message?: string;
}

const SUIT: Record<string, string> = { s: '♠', h: '♥', d: '♦', c: '♣' }
function Card({ code, hidden = false }: { code?: string; hidden?: boolean }) {
  if (hidden || !code) return <div className="playing-card back">◆</div>
  const rank = code[0] === 'T' ? '10' : code[0]
  const suit = SUIT[code[1]] || code[1]
  return <div className={`playing-card ${code[1] === 'h' || code[1] === 'd' ? 'red' : ''}`}><b>{rank}</b><span>{suit}</span></div>
}

function App() {
  const [count, setCount] = useState(6)
  const [stack, setStack] = useState(1000)
  const [smallBlind, setSmallBlind] = useState(5)
  const [bigBlind, setBigBlind] = useState(10)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [game, setGame] = useState<EventData | null>(null)
  const [busy, setBusy] = useState(false)
  const [amount, setAmount] = useState(20)
  const [notice, setNotice] = useState('人数と初期チップを設定して開始してください')
  const [lastResult, setLastResult] = useState<EventData | null>(null)
  const [showdownPending, setShowdownPending] = useState(false)

  async function start() {
    setBusy(true); setNotice('テーブルを準備しています…'); setLastResult(null)
    try {
      const res = await fetch('/api/sessions', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ player_count: count, starting_stack: stack, small_blind: smallBlind, big_blind: bigBlind }) })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || '開始できませんでした')
      setSessionId(data.session_id); setGame(null); setShowdownPending(false); setNotice('ゲームを開始しました')
    } catch (e) { setNotice(e instanceof Error ? e.message : '通信エラー') }
    finally { setBusy(false) }
  }

  useEffect(() => {
    if (!sessionId) return
    let cancelled = false
    async function poll() {
      while (!cancelled) {
        try {
          const res = await fetch(`/api/sessions/${sessionId}/events?timeout=10`)
          const event: EventData = await res.json()
          if (cancelled) break
          if (event.type === 'your_turn') {
            setShowdownPending(false); setGame(event); setNotice(`${event.street?.toUpperCase()}：あなたのアクションです`)
            const legal = event.legal_actions || {}
            setAmount(Number(legal.min_raise_to || legal.min_bet_to || 20))
          } else if (event.type === 'showdown_decision') {
            setShowdownPending(true)
            setGame(prev => prev ? { ...prev, type: 'showdown_decision', board: event.board || prev.board, legal_actions: {} } : prev)
            setNotice(event.message || 'ショーするかマックするか選択してください')
          } else if (event.type === 'hand_complete') {
            setShowdownPending(false); setLastResult(event); setGame({ ...event, legal_actions: {} }); setNotice(`ハンド終了：勝者 ${event.winner_names?.join(', ') || 'なし'}`)
          } else if (event.type === 'game_over') {
            setNotice('ゲーム終了'); setGame(event)
          } else if (event.type === 'error') setNotice(event.message || 'ゲームエラー')
        } catch { if (!cancelled) setNotice('サーバーとの接続を再試行しています…') }
      }
    }
    void poll()
    return () => { cancelled = true }
  }, [sessionId])

  async function act(type: string, value?: number) {
    if (!sessionId || busy) return
    setBusy(true)
    try {
      const res = await fetch(`/api/sessions/${sessionId}/actions`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ type, ...(value === undefined ? {} : { amount: value }) }) })
      const data = await res.json(); if (!res.ok) throw new Error(data.detail || '操作できませんでした')
      // Keep the latest table state visible while AI actions are processed.
      // In particular, showdown_decision may arrive before another your_turn.
      setNotice('AIのアクションを処理しています…')
    } catch (e) { setNotice(e instanceof Error ? e.message : '操作エラー') }
    finally { setBusy(false) }
  }
  async function decideShowdown(decision: 'show' | 'muck') {
    if (!sessionId || busy) return
    setBusy(true)
    try {
      const res = await fetch(`/api/sessions/${sessionId}/showdown-decision`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ decision }) })
      const data = await res.json(); if (!res.ok) throw new Error(data.detail || '選択できませんでした')
      setShowdownPending(false); setNotice(decision === 'show' ? '手札を公開しました' : '手札をマックしました')
    } catch (e) { setNotice(e instanceof Error ? e.message : '選択エラー') }
    finally { setBusy(false) }
  }
  async function nextHand() {
    if (!sessionId) return
    await fetch(`/api/sessions/${sessionId}/next-hand`, { method: 'POST' })
    setNotice('次のハンドを準備しています…'); setLastResult(null)
  }

  const players = game?.players || []
  const ordered = useMemo(() => players.filter(p => !p.is_human).sort((a,b) => a.seat-b.seat), [players])
  const legal = game?.legal_actions || {}
  const canAct = game?.type === 'your_turn'
  const minAmount = Number(legal.min_raise_to || legal.min_bet_to || 1)
  const maxAmount = Number(legal.max_raise_to || 1)
  const boundedMin = Math.max(1, minAmount)
  const boundedMax = Math.max(boundedMin, maxAmount)
  const clampedAmount = Math.min(Math.max(Math.trunc(Number(amount) || boundedMin), boundedMin), boundedMax)
  const amountPresets = [
    { label: '最小', value: boundedMin },
    { label: '中間', value: Math.round(boundedMin + (boundedMax - boundedMin) * 0.5) },
    { label: '大きめ', value: Math.round(boundedMin + (boundedMax - boundedMin) * 0.75) },
    { label: '最大', value: boundedMax },
  ].filter((preset, index, all) => all.findIndex(item => item.value === preset.value) === index)

  return <main className="app-shell">
    <header className="topbar"><div><div className="eyebrow">NO-LIMIT HOLD’EM · PRACTICE TABLE</div><h1>テーブル</h1></div><div className="status-pill"><i/> {notice}</div></header>
    {!sessionId ? <section className="setup panel">
      <div><div className="eyebrow">NEW TABLE</div><h2>ゲーム設定</h2><p>仮想チップのみを使用する学習用テーブルです。</p></div>
      <div className="settings-grid">
        <label>プレイヤー人数 <strong>{count}人</strong><input type="range" min="2" max="9" value={count} onChange={e=>setCount(Number(e.target.value))}/><small>人間1人 + AI {count-1}人</small></label>
        <label>初期チップ <strong>{stack.toLocaleString()}</strong><input type="number" min="100" max="100000" step="100" value={stack} onChange={e=>setStack(Number(e.target.value))}/></label>
        <label>スモールブラインド<input type="number" min="1" value={smallBlind} onChange={e=>setSmallBlind(Number(e.target.value))}/></label>
        <label>ビッグブラインド<input type="number" min="1" value={bigBlind} onChange={e=>setBigBlind(Number(e.target.value))}/></label>
      </div>
      <button className="primary start" disabled={busy || bigBlind < smallBlind || count < 2} onClick={start}>テーブルを開始 <span>→</span></button>
    </section> : <>
      <section className="table-wrap">
        <div className="table-felt">
          <div className="table-inner">
            <div className="table-label">POKER LEARNING TABLE</div>
            <div className="pot-display"><span>POT</span><strong>{(game?.type === 'your_turn' ? (game.pot ?? 0) : Object.values(lastResult?.payouts || {}).reduce((a,b)=>a+b,0)).toLocaleString()}</strong></div>
            <div className="community-cards">{Array.from({length:5},(_,i)=><Card key={i} code={game?.board?.[i]}/>)}</div>
            <div className="street-label">{game?.street?.toUpperCase() || (lastResult ? 'HAND COMPLETE' : 'WAITING')}</div>
          </div>
          {ordered.map((p)=>{
            // Seat 0 (human) stays at the bottom. AI seats follow the engine's
            // clockwise seat numbering around the table.
            const n = Math.max(2, players.length)
            const angle = (90 + (360/n)*p.seat) * Math.PI/180
            const x = 50 + Math.cos(angle)*42
            const y = 50 + Math.sin(angle)*42
            return <div key={p.player_id} className={`seat ai-seat ${p.folded?'is-folded':''} ${p.action_status==='ACTED'?'has-acted':''}`} style={{left:`${x}%`,top:`${y}%`}}>
              <div className="avatar">{p.name.slice(0,1)}{p.is_button && <small className="dealer-marker">D</small>}</div>
              <div className="seat-info"><b>{p.name} <i className="position-tag">{p.position || '—'}</i></b><span>{p.stack.toLocaleString()} chips</span><span className="seat-status">{p.action_status || '—'}{p.last_action ? ` · ${p.last_action.toUpperCase()}` : ''}</span>{p.street_bet > 0 && <em>BET {p.street_bet.toLocaleString()}</em>}</div>
              <div className="mini-cards">{[0,1].map(i=><Card key={i} code={lastResult?.revealed_hole_cards?.[p.player_id]?.[i]} hidden={!lastResult?.revealed_hole_cards?.[p.player_id]}/>)}</div>
            </div>
          })}
          {(()=>{ const human = players.find(p=>p.is_human); return <div className="seat human-seat">
            <div className="human-cards">{(game?.hole_cards || []).map((c,i)=><Card key={i} code={c} hidden={!!lastResult && !lastResult.revealed_hole_cards?.[game?.human_player_id || 'p1']}/>)}</div>
            <div className="avatar human-avatar">You{human?.is_button && <small className="dealer-marker">D</small>}</div>
            <div className="seat-info"><b>あなた <i className="position-tag">{human?.position || game?.human_position || '—'}</i></b><span>{human?.stack?.toLocaleString() ?? stack.toLocaleString()} chips</span><span className="seat-status">{human?.action_status || '—'}</span>{(human?.street_bet ?? 0)>0 && <em>BET {human!.street_bet.toLocaleString()}</em>}</div>
          </div> })()}
        </div>
      </section>
      <section className="below-table">
        <div className="panel action-panel"><div className="panel-heading"><div><div className="eyebrow">YOUR MOVE</div><h2>アクション</h2></div><span className="to-call">コール額 <b>{game?.to_call ?? 0}</b></span></div>
          <div className="action-buttons">
            <button disabled={!canAct || busy || !legal.can_fold} onClick={()=>act('fold')}>フォールド</button>
            <button disabled={!canAct || busy || !legal.can_check} onClick={()=>act('check')}>チェック</button>
            <button disabled={!canAct || busy || !legal.can_call} onClick={()=>act('call')}>コール {game?.to_call ? `(${game.to_call})` : ''}</button>
            <button disabled={!canAct || busy || !legal.can_all_in} onClick={()=>act('all_in')}>オールイン</button>
          </div>
          <div className="raise-controls">
            <div className="raise-heading"><label htmlFor="bet-amount">ベット / レイズ額</label><span>合計額（チップ）</span></div>
            <div className="amount-presets">
              {amountPresets.map(preset => <button key={preset.label} type="button" className={clampedAmount === preset.value ? 'selected' : ''} disabled={!canAct || busy || !(legal.can_bet || legal.can_raise)} onClick={() => setAmount(preset.value)}>{preset.label}<small>{preset.value.toLocaleString()}</small></button>)}
            </div>
            <div className="amount-entry">
              <input id="bet-amount" type="number" min={boundedMin} max={boundedMax} step="1" value={amount} disabled={!canAct || busy || !(legal.can_bet || legal.can_raise)} onChange={e=>setAmount(e.target.value === '' ? 0 : Number(e.target.value))} onBlur={()=>setAmount(clampedAmount)} />
              <input aria-label="ベット額スライダー" type="range" min={boundedMin} max={boundedMax} step="1" value={clampedAmount} disabled={!canAct || busy || !(legal.can_bet || legal.can_raise)} onChange={e=>setAmount(Number(e.target.value))}/>
              <button className="primary" disabled={!canAct || busy || !(legal.can_bet || legal.can_raise) || !Number.isInteger(amount) || amount < boundedMin || amount > boundedMax} onClick={()=>act(legal.can_bet?'bet':'raise',amount)}>{legal.can_bet?'ベット':'レイズ'}</button>
            </div>
            <small className="amount-range">選択可能な範囲：{boundedMin.toLocaleString()} ～ {boundedMax.toLocaleString()}</small>
          </div>
          {showdownPending && <div className="showdown-choice"><b>ショーダウン：手札を公開しますか？</b><p>勝敗とチップの分配は確定済みです。敗者は公開・マックを選べます。勝者の手札はポット獲得のため公開されます。</p><button className="primary" disabled={busy} onClick={()=>decideShowdown('show')}>ショーする</button><button disabled={busy} onClick={()=>decideShowdown('muck')}>マックする</button></div>}
          {lastResult && <div className="result-strip">ハンド結果：{lastResult.winner_names?.join(', ') || '勝者なし'} が獲得　<button onClick={nextHand}>次のハンドへ</button></div>}
        </div>
        <aside className="panel info-panel"><div className="eyebrow">TABLE INFO</div><h3>ゲーム情報</h3><div className="info-line"><span>ハンド</span><b>{game?.hand_id || lastResult?.hand_id || '—'}</b></div><div className="info-line"><span>ストリート</span><b>{game?.street || '—'}</b></div><div className="info-line"><span>現在のベット</span><b>{game?.current_bet ?? '—'}</b></div><div className="info-line"><span>あなたのポジション</span><b>{game?.human_position || players.find(p=>p.is_human)?.position || '—'}</b></div><div className="info-line"><span>ボタン位置</span><b>{players.find(p=>p.is_button)?.name || '—'}</b></div><div className="info-line"><span>アクション順</span><b>{players.filter(p=>p.action_status==='ACTED').map(p=>p.position).join(' → ') || 'まだなし'}</b></div><p className="disclaimer">チップはゲーム内の表示用で、購入・換金・譲渡できません。</p></aside>
      </section>
    </>}
    <footer>POKER LEARNING TABLE <span>PLAY-MONEY SIMULATION</span></footer>
  </main>
}

createRoot(document.getElementById('root')!).render(<React.StrictMode><App /></React.StrictMode>)
