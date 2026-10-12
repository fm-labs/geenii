type PathStyle =
  | { kind: "line" }
  | { kind: "curved" }
  | { kind: "cubicH"; strength?: number }
  | { kind: "cubicV"; strength?: number }
  | { kind: "quad"; bend?: number }
  | { kind: "elbow"; mode?: "HV" | "VH" }
  | { kind: "roundedElbowHV"; r?: number }
  | { kind: "arc"; curvature?: number };

export function buildPathD(
  x1:number,y1:number,x2:number,y2:number,
  style: PathStyle
){
  switch (style.kind) {
    case "line": return dLine(x1,y1,x2,y2);
    case "curved": return dCurved(x1,y1,x2,y2);
    case "cubicH": return dCubicHorizontal(x1,y1,x2,y2, style.strength ?? 0.5);
    case "cubicV": return dCubicVertical(x1,y1,x2,y2, style.strength ?? 0.5);
    case "quad": return dQuadratic(x1,y1,x2,y2, style.bend ?? 0.2);
    case "elbow": return dElbow(x1,y1,x2,y2, style.mode ?? "HV");
    case "roundedElbowHV": return dRoundedElbowHV(x1,y1,x2,y2, style.r ?? 12);
    case "arc": return dArc(x1,y1,x2,y2, style.curvature ?? 0.6);
  }
}

export const dLine = (x1:number,y1:number,x2:number,y2:number) =>
  `M ${x1} ${y1} L ${x2} ${y2}`;

export const dCurved = (x1:number,y1:number,x2:number,y2:number) => {
  const midX = (x1 + x2) / 2;
  return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
}


export function dCubicHorizontal(
  x1:number,y1:number,x2:number,y2:number,
  strength = 0.5 // 0..1
){
  const dx = x2 - x1;
  const c = Math.abs(dx) * strength;
  const c1x = x1 + c;
  const c2x = x2 - c;
  return `M ${x1} ${y1} C ${c1x} ${y1}, ${c2x} ${y2}, ${x2} ${y2}`;
}

export function dCubicVertical(
  x1:number,y1:number,x2:number,y2:number,
  strength = 0.5
){
  const dy = y2 - y1;
  const c = Math.abs(dy) * strength;
  const c1y = y1 + c;
  const c2y = y2 - c;
  return `M ${x1} ${y1} C ${x1} ${c1y}, ${x2} ${c2y}, ${x2} ${y2}`;
}

export function dQuadratic(
  x1:number,y1:number,x2:number,y2:number,
  bend = 0.2 // fraction of distance
){
  const dx = x2 - x1;
  const dy = y2 - y1;

  // perpendicular unit-ish (no need to normalize perfectly)
  const px = -dy;
  const py = dx;

  const mx = (x1 + x2) / 2;
  const my = (y1 + y2) / 2;

  // amount of perpendicular offset
  const dist = Math.hypot(dx, dy);
  const k = dist * bend / (Math.hypot(px, py) || 1);

  const cx = mx + px * k;
  const cy = my + py * k;

  return `M ${x1} ${y1} Q ${cx} ${cy}, ${x2} ${y2}`;
}

type ElbowMode = "HV" | "VH";

export function dElbow(
  x1:number,y1:number,x2:number,y2:number,
  mode:ElbowMode = "HV"
){
  if (mode === "HV") {
    const mx = (x1 + x2) / 2;
    return `M ${x1} ${y1} L ${mx} ${y1} L ${mx} ${y2} L ${x2} ${y2}`;
  } else {
    const my = (y1 + y2) / 2;
    return `M ${x1} ${y1} L ${x1} ${my} L ${x2} ${my} L ${x2} ${y2}`;
  }
}

export function dRoundedElbowHV(
  x1:number,y1:number,x2:number,y2:number,
  r = 12
){
  const mx = (x1 + x2) / 2;

  // Clamp radius so it can’t exceed segment lengths
  const r1 = Math.min(r, Math.abs(mx - x1), Math.abs(y2 - y1));
  const r2 = Math.min(r, Math.abs(x2 - mx), Math.abs(y2 - y1));

  // Determine directions
  const sx = mx >= x1 ? 1 : -1;
  const sy = y2 >= y1 ? 1 : -1;

  const p1x = mx - sx * r1;  // approach first corner
  const p2y = y2 - sy * r2;  // approach second corner

  return [
    `M ${x1} ${y1}`,
    `L ${p1x} ${y1}`,
    `Q ${mx} ${y1} ${mx} ${y1 + sy * r1}`,
    `L ${mx} ${p2y}`,
    `Q ${mx} ${y2} ${mx + sx * r2} ${y2}`,
    `L ${x2} ${y2}`,
  ].join(" ");
}

export function dArc(
  x1:number,y1:number,x2:number,y2:number,
  curvature = 0.6 // scales radius
){
  const dx = x2 - x1, dy = y2 - y1;
  const dist = Math.hypot(dx, dy);
  const r = Math.max(1, dist * curvature);

  // sweep-flag toggles which side the arc goes
  const sweep = 1; // or 0 to flip
  return `M ${x1} ${y1} A ${r} ${r} 0 0 ${sweep} ${x2} ${y2}`;
}
