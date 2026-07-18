'use client';

import * as React from 'react';
import './v2.css';
import { Flame, Sparkles, Pause, SkipForward, ArrowRight, Zap } from 'lucide-react';
import { CountingNumber } from '@/components/animate-ui/primitives/texts/counting-number';
import { Button } from '@/components/animate-ui/primitives/buttons/button';
import { supabase } from '@/lib/supabase';

type GoalRow = { name: string; due: string; pct: number; done: number; total: number; status: 'go' | 'rev'; fx: 'plasma' | 'wave' | 'none'; ooze: string };

const MOCK_GOALS: GoalRow[] = [
  { name: 'System Design', due: 'due in 6 days', pct: 78, done: 14, total: 18, status: 'go', fx: 'plasma', ooze: 'linear-gradient(135deg,#5fa6bf,#6f73b2,#9468b0)' },
  { name: 'Rust Fundamentals', due: 'due in 19 days', pct: 38, done: 6, total: 16, status: 'go', fx: 'wave', ooze: 'linear-gradient(135deg,#82b89a,#5fa6bf,#6f73b2)' },
  { name: 'ML Interview Prep', due: 'due in 3 days', pct: 20, done: 3, total: 15, status: 'rev', fx: 'none', ooze: 'linear-gradient(135deg,#c47a96,#9468b0,#6f73b2)' },
];
const QUIZZES = [
  { name: 'CAP theorem', meta: 'SYSTEM DESIGN · 2H AGO', score: 92, k: 'hi' },
  { name: 'Ownership & borrowing', meta: 'RUST · YESTERDAY', score: 74, k: 'mid' },
  { name: 'Gradient descent', meta: 'ML PREP · 2 DAYS AGO', score: 58, k: 'lo' },
  { name: 'Load balancing', meta: 'SYSTEM DESIGN · 3 DAYS AGO', score: 88, k: 'hi' },
];
const PLAN = [
  { t: '08:30', tx: 'Morning review · flashcards', tg: 'done', s: 'done' },
  { t: '10:00', tx: 'Rust · ownership deep dive', tg: 'done', s: 'done' },
  { t: '14:00', tx: 'System Design · CAP theorem', tg: 'now', s: 'now' },
  { t: '16:30', tx: 'ML · gradient descent retry', tg: 'queued', s: '' },
  { t: '19:00', tx: 'Quiz · sharding strategies', tg: 'queued', s: '' },
];
const dash = (r: number, pct: number) => { const c = 2 * Math.PI * r; return { dasharray: c, dashoffset: c * (1 - pct / 100) }; };

export default function V2Page() {
  const [streak, setStreak] = React.useState(14);
  const [goals, setGoals] = React.useState<GoalRow[]>(MOCK_GOALS);
  const rootRef = React.useRef<HTMLDivElement>(null);

  // live data with graceful fallback to mock
  React.useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const [g, s] = await Promise.all([
          supabase.from('goals').select('*').order('created_at'),
          supabase.from('settings').select('*').eq('id', 1).single(),
        ]);
        if (!alive) return;
        if (s.data?.streak != null) setStreak(s.data.streak);
        if (g.data && g.data.length) {
          const mapped: GoalRow[] = g.data.slice(0, 3).map((row: any, i: number) => ({
            name: row.name ?? 'Goal',
            due: row.target_date ? `due ${row.target_date}` : 'no deadline',
            pct: row.completed_topic_count && row.topic_count ? Math.round((row.completed_topic_count / row.topic_count) * 100) : MOCK_GOALS[i % 3].pct,
            done: row.completed_topic_count ?? MOCK_GOALS[i % 3].done,
            total: row.topic_count ?? MOCK_GOALS[i % 3].total,
            status: 'go',
            fx: MOCK_GOALS[i % 3].fx,
            ooze: MOCK_GOALS[i % 3].ooze,
          }));
          setGoals(mapped);
        }
      } catch { /* keep mock */ }
    })();
    return () => { alive = false; };
  }, []);

  // rAF-coalesced tilt + sheen + cursor glow
  React.useEffect(() => {
    const root = rootRef.current; if (!root) return;
    const glow = root.querySelector<HTMLElement>('.v2glow');
    const cards = Array.from(root.querySelectorAll<HTMLElement>('.v2card.tilt'));
    let px = 0, py = 0, hc: HTMLElement | null = null, raf = 0;
    const apply = () => {
      raf = 0;
      if (glow) glow.style.transform = `translate(${px}px,${py}px) translate(-50%,-50%)`;
      if (hc) {
        const r = hc.getBoundingClientRect();
        const mx = (px - r.left) / r.width, my = (py - r.top) / r.height;
        hc.style.transform = `perspective(900px) rotateY(${(mx - .5) * 7}deg) rotateX(${(.5 - my) * 7}deg) translateY(-2px)`;
        hc.style.setProperty('--mx', mx * 100 + '%');
        hc.style.setProperty('--my', my * 100 + '%');
      }
    };
    const onMove = (e: PointerEvent) => { px = e.clientX; py = e.clientY; if (!raf) raf = requestAnimationFrame(apply); };
    window.addEventListener('pointermove', onMove, { passive: true });
    const enter = (c: HTMLElement) => () => (hc = c);
    const leave = (c: HTMLElement) => () => { if (hc === c) { hc = null; c.style.transform = ''; } };
    const subs = cards.map((c) => { const en = enter(c), lv = leave(c); c.addEventListener('pointerenter', en); c.addEventListener('pointerleave', lv); return () => { c.removeEventListener('pointerenter', en); c.removeEventListener('pointerleave', lv); }; });
    return () => { window.removeEventListener('pointermove', onMove); subs.forEach((u) => u()); };
  }, []);

  const cells = [0.82, 0.45, 0.9, 0.12, 0.6, 0.74, 0.33, 0.95, 0.5, 0.08, 0.68, 0.4, 0.86, 0.55];
  const focusRing = dash(74, 68);

  return (
    <div className="v2root" ref={rootRef}>
      {/* svg filters */}
      <svg width="0" height="0" style={{ position: 'absolute' }} aria-hidden>
        <filter id="v2goo"><feGaussianBlur in="SourceGraphic" stdDeviation="9" result="b" /><feColorMatrix in="b" mode="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -9" /></filter>
        <filter id="v2grain"><feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves={2} stitchTiles="stitch" /><feColorMatrix type="saturate" values="0" /></filter>
        <linearGradient id="v2rg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#5fa6bf" /><stop offset=".5" stopColor="#6f73b2" /><stop offset="1" stopColor="#9468b0" /></linearGradient>
      </svg>

      <div className="v2bg"><div className="blob r1" /><div className="blob r2" /><div className="g" /><div className="dark" /></div>
      <div className="v2glow" />
      <div className="v2grain" />

      <div className="v2main">
          <div className="v2top">
            <div className="v2hello">
              <div className="eyebrow">Tuesday · 27 June · risograph</div>
              <h1>Good evening, <span className="gr">Shekhar.</span></h1>
              <p>You&apos;re 2 topics away from finishing <b style={{ color: '#fff' }}>System Design</b> this week.</p>
            </div>
            <div className="v2card tilt" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#c9ac6a,#c47a96,#9468b0)' }}>
              <div className="v2glass streak"><div className="sheen" />
                <span className="flame"><Flame size={28} fill="#e08a4d" /></span>
                <div className="body"><div className="n"><CountingNumber number={streak} delay={200} /></div><div className="l">day streak</div></div>
              </div>
            </div>
          </div>

          <div className="grid2">
            <div className="v2card tilt ringfx" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#5fa6bf,#6f73b2,#9468b0)' }}>
              <div className="v2glass focus"><div className="sheen" />
                <div className="ringc body">
                  <svg width="172" height="172" viewBox="0 0 172 172"><circle cx="86" cy="86" r="74" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="11" /><circle cx="86" cy="86" r="74" fill="none" stroke="url(#v2rg)" strokeWidth="11" strokeLinecap="round" strokeDasharray={focusRing.dasharray} strokeDashoffset={focusRing.dashoffset} style={{ filter: 'drop-shadow(0 0 8px rgba(111,115,178,.6))' }} /></svg>
                  <div className="lab"><div className="time">24:18</div><div className="sub">focus · deep work</div></div>
                </div>
                <div className="body" style={{ flex: 1 }}>
                  <div className="tag"><Zap size={13} /> Active session</div>
                  <h2>Consistency &amp; CAP theorem</h2>
                  <div className="desc">Picking up where you left off. 18 minutes of deep focus left — then a 5-minute breather.</div>
                  <div className="btnrow">
                    <Button hoverScale={1.04} tapScale={0.96} className="btn primary"><Pause size={15} /> Pause</Button>
                    <Button hoverScale={1.04} tapScale={0.96} className="btn"><SkipForward size={15} /> Skip topic</Button>
                  </div>
                </div>
              </div>
            </div>
            <div className="v2card tilt" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#c47a96,#c28a5a,#9468b0)' }}>
              <div className="v2glass suggest"><div className="sheen" /><div className="fxfoil" />
                <div className="body"><div className="tag"><Sparkles size={13} /> Suggested next</div><h3>Database sharding strategies</h3><p>You&apos;re ready to push into horizontal scaling. ~25 min read + a 4-question check.</p></div>
                <Button hoverScale={1.05} tapScale={0.95} className="pill body">START IN FOCUS <ArrowRight size={13} /></Button>
              </div>
            </div>
          </div>

          <div className="v2sect"><h2>Active goals</h2><span className="lk">view all →</span></div>
          <div className="grid3">
            {goals.map((g, i) => { const r = dash(19, g.pct); return (
              <div key={i} className="v2card tilt" style={{ ['--ooze' as any]: g.ooze }}>
                <div className="v2glass goal"><div className="sheen" />
                  {g.fx === 'plasma' && <div className="fxplasma"><i /><i /><i /></div>}
                  {g.fx === 'wave' && <div className="fxwave" />}
                  <div className="body">
                    <div className="gt"><div><div className="gn">{g.name}</div><div className="due">{g.due}</div></div>
                      <div className="mring"><svg width="46" height="46" viewBox="0 0 46 46"><circle cx="23" cy="23" r="19" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="5" /><circle cx="23" cy="23" r="19" fill="none" stroke="url(#v2rg)" strokeWidth="5" strokeLinecap="round" strokeDasharray={r.dasharray} strokeDashoffset={r.dashoffset} /></svg><div className="pc"><CountingNumber number={g.pct} delay={250 + i * 120} />%</div></div>
                    </div>
                    <div className="bar"><i style={{ width: `${g.pct}%`, background: g.status === 'rev' ? 'linear-gradient(90deg,#c47a96,#9468b0)' : undefined }} /></div>
                    <div className="gf"><span>{g.done} / {g.total} topics</span><span className={`chip ${g.status}`}>{g.status === 'rev' ? 'behind' : 'on track'}</span></div>
                  </div>
                </div>
              </div>
            ); })}
          </div>

          <div className="gridplan mt">
            <div className="v2card tilt ringfx" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#82b89a,#5fa6bf,#9468b0)' }}>
              <div className="v2glass plan"><div className="sheen" /><div className="body"><h4>Today&apos;s plan</h4><div className="tl">
                {PLAN.map((p, i) => <div key={i} className={`tlr ${p.s}`}><span className="t">{p.t}</span><span className="dot" /><span className="tx">{p.tx}</span><span className="tg">{p.tg}</span></div>)}
              </div></div></div>
            </div>
            <div className="v2card tilt" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#6f73b2,#7a61a6,#9468b0)' }}>
              <div className="v2glass mom"><div className="sheen" /><div className="body"><h4>Weekly momentum</h4><div className="hsub">hrs of deep work</div>
                <div className="bars">{[40, 65, 50, 85, 72, 95, 60].map((h, i) => <i key={i} style={{ height: `${h}%` }} />)}</div>
                <div className="blab">{['M', 'T', 'W', 'T', 'F', 'S', 'S'].map((d, i) => <span key={i}>{d}</span>)}</div>
              </div></div>
            </div>
          </div>

          <div className="grid2 mt">
            <div className="v2card tilt" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#5fa6bf,#6f73b2,#7a61a6)' }}>
              <div className="v2glass quiz"><div className="sheen" /><div className="body">
                <div className="v2sect" style={{ margin: '0 0 6px' }}><h2 style={{ fontSize: 16 }}>Recent quizzes</h2></div>
                {QUIZZES.map((q, i) => <div key={i} className="qi"><div><div className="qn">{q.name}</div><div className="qm">{q.meta}</div></div><span className={`sc ${q.k}`}><CountingNumber number={q.score} delay={300 + i * 100} />%</span></div>)}
              </div></div>
            </div>
            <div className="v2card tilt" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#8bbecb,#5fa6bf,#9468b0)' }}>
              <div className="v2glass heat"><div className="sheen" /><div className="body"><h4>Focus heatmap</h4><div className="hsub">last 14 days · 9.4 hrs deep work</div>
                <div className="cells">{cells.map((v, i) => <div key={i} className="cell" style={{ background: v < .18 ? 'rgba(255,255,255,.05)' : `linear-gradient(135deg,rgba(95,166,191,${v * .9 + .05}),rgba(148,104,176,${v * .9 + .05}))`, animationDelay: `${i * .12}s` }} />)}</div>
              </div></div>
            </div>
          </div>

          <div className="gridtri mt">
            <div className="v2card tilt" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#c47a96,#5fa6bf,#9468b0)' }}>
              <div className="v2glass tutor"><div className="sheen" /><div className="body"><div className="tag"><Sparkles size={13} /> AI tutor</div><h3>Stuck on something?</h3><p>Ask anything about your goals. I know what you&apos;ve studied and where you slipped.</p></div>
                <div className="ask body"><span>Explain CAP theorem like I&apos;m 5</span></div>
              </div>
            </div>
            <div className="v2card tilt" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#c9ac6a,#c47a96,#9468b0)' }}>
              <div className="v2glass xp"><div className="sheen" /><div className="body"><div className="lvl">Level 12 · Scholar</div><div className="big"><CountingNumber number={4820} delay={300} /></div><div className="lvl">XP this season</div><div className="bar"><i style={{ width: '64%' }} /></div><div className="nx">680 XP to Level 13</div></div></div>
            </div>
            <div className="v2card tilt" style={{ ['--ooze' as any]: 'linear-gradient(135deg,#82b89a,#5fa6bf,#6f73b2)' }}>
              <div className="v2glass energy"><div className="sheen" />
                <div className="gauge body"><svg width="110" height="110" viewBox="0 0 110 110"><circle cx="55" cy="55" r="46" fill="none" stroke="rgba(255,255,255,.08)" strokeWidth="9" /><circle cx="55" cy="55" r="46" fill="none" stroke="url(#v2rg)" strokeWidth="9" strokeLinecap="round" strokeDasharray={dash(46, 73).dasharray} strokeDashoffset={dash(46, 73).dashoffset} style={{ filter: 'drop-shadow(0 0 6px rgba(95,166,191,.6))' }} /></svg><div className="v"><b><CountingNumber number={73} delay={350} />%</b><small>FOCUS</small></div></div>
                <div className="em body"><h4>Energy today</h4><p>Peak focus window detected 2–4pm. Schedule the hard topic now.</p></div>
              </div>
            </div>
          </div>
        </div>
      <div className="v2hud">LEARNIX // V2 · RISOGRAPH<br /><span className="rd">● </span>animate-ui + shadcn</div>
    </div>
  );
}
