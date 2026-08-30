import { AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame } from 'remotion';

const SANS = '"Microsoft YaHei", "PingFang SC", system-ui, sans-serif';
const PINE = '#104737';
const AMBER = '#c58b35';
const els = [
  { file: 'card1.png', x: 90, y: 110, w: 420, h: 130, dx: -500, dy: -120, r: -5 },
  { file: 'card2.png', x: 1420, y: 110, w: 420, h: 130, dx: 500, dy: -160, r: 4 },
  { file: 'card4.png', x: 80, y: 760, w: 240, h: 110, dx: -430, dy: 260, r: 4 },
  { file: 'card8.png', x: 1530, y: 800, w: 250, h: 110, dx: 430, dy: 260, r: -4 },
  { file: 'paper1.png', x: 1220, y: 700, w: 560, h: 260, dx: 450, dy: 300, r: -3 },
  { file: 'paper3.png', x: 130, y: 630, w: 560, h: 260, dx: -450, dy: 300, r: 3 },
  { file: 'paper2.png', x: 650, y: 75, w: 620, h: 260, dx: 0, dy: -420, r: 0 },
  { file: 'card6.png', x: 380, y: 820, w: 390, h: 120, dx: -100, dy: 360, r: -2 },
  { file: 'card10.png', x: 1120, y: 820, w: 390, h: 120, dx: 100, dy: 360, r: 2 },
];
const dust = Array.from({ length: 20 }, (_, i) => ({ x: (i * 439 + 137) % 1920, y: (i * 613 + 271) % 1080, s: 2 + i % 3, o: .14 + (i % 5) * .04 }));

export const SceneOutroLive: React.FC = () => {
  const frame = useCurrentFrame();
  const recede = interpolate(frame, [42, 52], [1, .82], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const rule = interpolate(frame, [58, 70], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const tag = interpolate(frame, [68, 82], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const crane = interpolate(frame, [0, 40], [1.06, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.3, 0, .2, 1) });
  return <AbsoluteFill style={{ background: 'radial-gradient(1000px 620px at 50% 48%,#fffaf0,#f3f0e8 72%)', overflow: 'hidden' }}>
    <AbsoluteFill style={{ transform: `perspective(1400px) rotateX(${4 * (crane - 1) / .06}deg) scale(${crane})`, opacity: recede }}>
      {els.map((el, i) => {
        const cue = 4 + i * 3;
        const t = interpolate(frame, [cue, cue + 12], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.34, 1.4, .44, 1) });
        return <div key={el.file} style={{ position: 'absolute', left: el.x, top: el.y, width: el.w, height: el.h, borderRadius: 14, overflow: 'hidden', transform: `translate(${el.dx * (1 - t)}px,${el.dy * (1 - t)}px) rotate(${el.r * (2 - t)}deg) scale(${1.1 - .1 * t})`, boxShadow: `0 ${10 + 24 * (1 - t)}px ${24 + 40 * (1 - t)}px rgba(16,71,55,.2)`, opacity: t }}>
          <Img src={staticFile(`textures/live/${el.file}`)} style={{ width: '100%', height: '100%' }} />
        </div>;
      })}
    </AbsoluteFill>
    {dust.map((d, i) => <div key={i} style={{ position: 'absolute', left: d.x + Math.sin(frame * .03 + i) * 12, top: ((d.y - frame * (.3 + i % 4 * .1)) % 1080 + 1080) % 1080, width: d.s, height: d.s, borderRadius: '50%', background: AMBER, opacity: d.o }} />)}
    <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center' }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ display: 'flex', justifyContent: 'center' }}>
          {'智景 ScenicMind'.split('').map((ch, i) => {
            const t = interpolate(frame, [42 + i * 1.7, 52 + i * 1.7], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.2, .75, .3, 1) });
            return <span key={i} style={{ whiteSpace: 'pre', display: 'inline-block', fontFamily: SANS, fontWeight: 800, fontSize: 126, color: PINE, opacity: t, transform: `translateY(${28 * (1 - t)}px) scale(${1.35 - .35 * t})`, filter: `blur(${8 * (1 - t)}px)` }}>{ch}</span>;
          })}
        </div>
        <div style={{ width: 280, height: 6, borderRadius: 3, background: AMBER, margin: '30px auto 0', transform: `scaleX(${rule})`, boxShadow: '0 0 24px rgba(197,139,53,.45)' }} />
        <div style={{ marginTop: 28, fontFamily: SANS, fontSize: 60, fontWeight: 700, letterSpacing: '.05em', color: '#4f6c61', opacity: tag }}>让每一次客流变化，都提前被看见</div>
      </div>
    </AbsoluteFill>
  </AbsoluteFill>;
};
