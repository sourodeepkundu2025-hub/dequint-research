OPENQASM 3.0;
include "stdgates.inc";
bit[8] c;
reset $2;
U(pi/2, 0, pi) $2;
reset $3;
reset $5;
cx $2, $5;
cx $0, $2;
U(pi/2, 0, pi) $0;
reset $7;
reset $8;
c[0] = measure $0;
reset $0;
reset $0;
c[1] = measure $2;
reset $2;
reset $2;
if (c[1]) {
  U(pi, 0, pi) $5;
}
if (c[0]) {
  U(0, 0, pi) $5;
}
cx $5, $3;
cx $3, $5;
cx $5, $3;
reset $5;
reset $5;
U(pi/2, 0, pi) $5;
cx $5, $8;
cx $3, $5;
U(pi/2, 0, pi) $3;
c[2] = measure $3;
reset $3;
reset $3;
c[3] = measure $5;
reset $5;
reset $5;
if (c[3]) {
  U(pi, 0, pi) $8;
}
if (c[2]) {
  U(0, 0, pi) $8;
}
cx $8, $7;
cx $7, $8;
cx $8, $7;
cx $7, $6;
reset $8;
reset $8;
U(pi/2, 0, pi) $8;
cx $8, $5;
cx $7, $8;
U(pi/2, 0, pi) $7;
c[4] = measure $7;
reset $7;
c[5] = measure $8;
if (c[5]) {
  U(pi, 0, pi) $5;
}
if (c[4]) {
  U(0, 0, pi) $5;
}
cx $5, $3;
cx $3, $5;
cx $5, $3;
reset $5;
reset $5;
U(pi/2, 0, pi) $5;
cx $5, $2;
cx $3, $5;
U(pi/2, 0, pi) $3;
reset $8;
c[6] = measure $3;
reset $3;
c[7] = measure $5;
if (c[7]) {
  U(pi, 0, pi) $2;
}
if (c[6]) {
  U(0, 0, pi) $2;
}
cx $2, $0;
cx $0, $2;
cx $2, $0;
reset $2;
reset $5;
