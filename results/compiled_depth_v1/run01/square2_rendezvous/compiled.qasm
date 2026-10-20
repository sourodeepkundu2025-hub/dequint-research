OPENQASM 3.0;
include "stdgates.inc";
bit[8] c;
reset $2;
U(pi/2, 0, pi) $2;
reset $6;
reset $7;
reset $8;
cx $2, $8;
cx $0, $2;
U(pi/2, 0, pi) $0;
reset $11;
U(pi/2, 0, pi) $11;
c[0] = measure $0;
reset $0;
reset $0;
c[1] = measure $2;
reset $2;
reset $2;
if (c[1]) {
  U(pi, 0, pi) $8;
}
if (c[0]) {
  U(0, 0, pi) $8;
}
cx $8, $6;
cx $6, $8;
cx $8, $6;
reset $8;
reset $8;
cx $11, $8;
cx $9, $11;
U(pi/2, 0, pi) $9;
c[2] = measure $9;
reset $9;
reset $9;
c[3] = measure $11;
if (c[3]) {
  U(pi, 0, pi) $8;
}
if (c[2]) {
  U(0, 0, pi) $8;
}
cx $8, $7;
cx $7, $8;
cx $8, $7;
cx $6, $7;
reset $8;
reset $8;
U(pi/2, 0, pi) $8;
cx $8, $2;
cx $6, $8;
U(pi/2, 0, pi) $6;
reset $11;
reset $11;
c[4] = measure $6;
reset $6;
c[5] = measure $8;
if (c[5]) {
  U(pi, 0, pi) $2;
}
if (c[4]) {
  U(0, 0, pi) $2;
}
cx $2, $0;
cx $0, $2;
cx $2, $0;
reset $2;
reset $8;
reset $8;
U(pi/2, 0, pi) $8;
cx $8, $11;
cx $7, $8;
U(pi/2, 0, pi) $7;
c[6] = measure $7;
reset $7;
c[7] = measure $8;
reset $8;
if (c[7]) {
  U(pi, 0, pi) $11;
}
if (c[6]) {
  U(0, 0, pi) $11;
}
cx $11, $9;
cx $9, $11;
cx $11, $9;
reset $11;
