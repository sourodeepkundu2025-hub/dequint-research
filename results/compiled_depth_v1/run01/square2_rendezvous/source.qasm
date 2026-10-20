OPENQASM 3.0;
include "stdgates.inc";
bit[8] c;
qubit[12] q;
reset q[2];
reset q[8];
reset q[6];
h q[2];
cx q[2], q[8];
cx q[0], q[2];
h q[0];
c[0] = measure q[0];
c[1] = measure q[2];
if (c[1]) {
  x q[8];
}
if (c[0]) {
  z q[8];
}
swap q[8], q[6];
reset q[0];
reset q[2];
reset q[8];
reset q[11];
reset q[8];
reset q[7];
h q[11];
cx q[11], q[8];
cx q[9], q[11];
h q[9];
c[2] = measure q[9];
c[3] = measure q[11];
if (c[3]) {
  x q[8];
}
if (c[2]) {
  z q[8];
}
swap q[8], q[7];
reset q[9];
reset q[11];
reset q[8];
cx q[6], q[7];
reset q[8];
reset q[2];
reset q[0];
h q[8];
cx q[8], q[2];
cx q[6], q[8];
h q[6];
c[4] = measure q[6];
c[5] = measure q[8];
if (c[5]) {
  x q[2];
}
if (c[4]) {
  z q[2];
}
swap q[2], q[0];
reset q[6];
reset q[8];
reset q[2];
reset q[8];
reset q[11];
reset q[9];
h q[8];
cx q[8], q[11];
cx q[7], q[8];
h q[7];
c[6] = measure q[7];
c[7] = measure q[8];
if (c[7]) {
  x q[11];
}
if (c[6]) {
  z q[11];
}
swap q[11], q[9];
reset q[7];
reset q[8];
reset q[11];
