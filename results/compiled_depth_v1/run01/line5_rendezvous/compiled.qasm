OPENQASM 3.0;
include "stdgates.inc";
bit[16] c;
reset $2;
U(pi/2, 0, pi) $2;
reset $3;
reset $5;
cx $2, $5;
cx $0, $2;
U(pi/2, 0, pi) $0;
reset $6;
reset $7;
reset $8;
reset $9;
reset $11;
reset $14;
U(pi/2, 0, pi) $14;
cx $14, $11;
cx $12, $14;
U(pi/2, 0, pi) $12;
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
cx $8, $6;
cx $6, $8;
cx $8, $6;
reset $8;
reset $8;
c[4] = measure $12;
reset $12;
reset $12;
c[5] = measure $14;
if (c[5]) {
  U(pi, 0, pi) $11;
}
if (c[4]) {
  U(0, 0, pi) $11;
}
cx $11, $9;
cx $9, $11;
cx $11, $9;
reset $11;
reset $11;
U(pi/2, 0, pi) $11;
cx $11, $8;
cx $9, $11;
U(pi/2, 0, pi) $9;
reset $14;
reset $14;
c[6] = measure $9;
reset $9;
reset $9;
c[7] = measure $11;
if (c[7]) {
  U(pi, 0, pi) $8;
}
if (c[6]) {
  U(0, 0, pi) $8;
}
cx $8, $7;
cx $7, $8;
cx $8, $7;
cx $6, $7;
reset $8;
reset $8;
U(pi/2, 0, pi) $8;
cx $8, $5;
cx $6, $8;
U(pi/2, 0, pi) $6;
reset $11;
reset $11;
c[8] = measure $6;
reset $6;
c[9] = measure $8;
if (c[9]) {
  U(pi, 0, pi) $5;
}
if (c[8]) {
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
reset $8;
U(pi/2, 0, pi) $8;
cx $8, $11;
cx $7, $8;
U(pi/2, 0, pi) $7;
c[10] = measure $3;
reset $3;
c[11] = measure $5;
if (c[11]) {
  U(pi, 0, pi) $2;
}
if (c[10]) {
  U(0, 0, pi) $2;
}
cx $2, $0;
cx $0, $2;
cx $2, $0;
reset $2;
reset $5;
c[12] = measure $7;
reset $7;
c[13] = measure $8;
reset $8;
if (c[13]) {
  U(pi, 0, pi) $11;
}
if (c[12]) {
  U(0, 0, pi) $11;
}
cx $11, $9;
cx $9, $11;
cx $11, $9;
reset $11;
reset $11;
U(pi/2, 0, pi) $11;
cx $11, $14;
cx $9, $11;
U(pi/2, 0, pi) $9;
c[14] = measure $9;
reset $9;
c[15] = measure $11;
reset $11;
if (c[15]) {
  U(pi, 0, pi) $14;
}
if (c[14]) {
  U(0, 0, pi) $14;
}
cx $14, $12;
cx $12, $14;
cx $14, $12;
reset $14;
