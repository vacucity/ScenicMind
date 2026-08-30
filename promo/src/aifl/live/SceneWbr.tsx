import { AbsoluteFill, Easing, interpolate, useCurrentFrame } from 'remotion';
import { PageCam, type CamKey } from './PageCam';
import layout from '../live-layout.json';

const block = layout.wbr.blocks[0];
const keys: CamKey[] = [
  { frame: 0, cx: 760, cy: 280, zoom: 1.35 },
  { frame: 52, cx: 800, cy: 370, zoom: 1.22 },
  { frame: 78, cx: 800, cy: 400, zoom: 1.18 },
  { frame: 110, cx: 800, cy: 400, zoom: 1.18 },
];

export const SceneWbr: React.FC = () => {
  const frame = useCurrentFrame();
  const wipe = interpolate(frame, [8, 52], [1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.4, 0, .6, 1) });
  const rail = interpolate(frame, [50, 64], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.out(Easing.cubic) });
  const pulse = interpolate(frame, [62, 72, 86], [0, 1, 0], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return <AbsoluteFill>
    <PageCam src="textures/live/wbr-full.png" pageH={1080} keys={keys} ease={Easing.bezier(.33, 0, .15, 1)}>
      {block ? <>
        <div style={{ position: 'absolute', left: block.x + block.w * (1 - wipe), top: block.y, width: block.w * wipe, height: block.h, background: '#fff', transformOrigin: 'right center' }} />
        <div style={{ position: 'absolute', left: block.x + block.w * (1 - wipe) - 2, top: block.y + 10, width: 3, height: Math.max(24, block.h - 20), background: '#c58b35', opacity: wipe > 0 ? 1 : 0 }} />
        <div style={{ position: 'absolute', left: block.x + 20, top: block.y + 112, width: 340 * rail, height: 18, borderRadius: 9, background: '#dcebe2', boxShadow: `0 0 ${24 * pulse}px rgba(197,139,53,.38)` }} />
      </> : null}
    </PageCam>
    <div style={{ position: 'absolute', right: 92, top: 80, padding: '18px 24px', borderRadius: 12, background: '#104737', color: '#fff', font: '700 24px "Microsoft YaHei",sans-serif', letterSpacing: '.08em', opacity: interpolate(frame, [16, 28], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' }) }}>AI 解释每一次预测</div>
  </AbsoluteFill>;
};
