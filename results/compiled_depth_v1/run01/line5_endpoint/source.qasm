OPENQASM 3.0;
include "stdgates.inc";
bit[16] c;
qubit[15] q;
reset q[2];
reset q[5];
reset q[3];
h q[2];
cx q[2], q[5];
cx q[0], q[2];
h q[0];
c[0] = measure q[0];
c[1] = measure q[2];
if (c[1]) {
  x q[5];
}
if (c[0]) {
  z q[5];
}
swap q[5], q[3];
reset q[0];
reset q[2];
reset q[5];
reset q[5];
reset q[8];
reset q[6];
h q[5];
cx q[5], q[8];
cx q[3], q[5];
h q[3];
c[2] = measure q[3];
c[3] = measure q[5];
if (c[3]) {
  x q[8];
}
if (c[2]) {
  z q[8];
}
swap q[8], q[6];
reset q[3];
reset q[5];
reset q[8];
reset q[8];
reset q[11];
reset q[9];
h q[8];
cx q[8], q[11];
cx q[6], q[8];
h q[6];
c[4] = measure q[6];
c[5] = measure q[8];
if (c[5]) {
  x q[11];
}
if (c[4]) {
  z q[11];
}
swap q[11], q[9];
reset q[6];
reset q[8];
reset q[11];
reset q[11];
reset q[14];
reset q[13];
h q[11];
cx q[11], q[14];
cx q[9], q[11];
h q[9];
c[6] = measure q[9];
c[7] = measure q[11];
if (c[7]) {
  x q[14];
}
if (c[6]) {
  z q[14];
}
swap q[14], q[13];
reset q[9];
reset q[11];
reset q[14];
cx q[13], q[12];
reset q[14];
reset q[11];
reset q[9];
h q[14];
cx q[14], q[11];
cx q[13], q[14];
h q[13];
c[8] = measure q[13];
c[9] = measure q[14];
if (c[9]) {
  x q[11];
}
if (c[8]) {
  z q[11];
}
swap q[11], q[9];
reset q[13];
reset q[14];
reset q[11];
reset q[11];
reset q[8];
reset q[6];
h q[11];
cx q[11], q[8];
cx q[9], q[11];
h q[9];
c[10] = measure q[9];
c[11] = measure q[11];
if (c[11]) {
  x q[8];
}
if (c[10]) {
  z q[8];
}
swap q[8], q[6];
reset q[9];
reset q[11];
reset q[8];
reset q[8];
reset q[5];
reset q[3];
h q[8];
cx q[8], q[5];
cx q[6], q[8];
h q[6];
c[12] = measure q[6];
c[13] = measure q[8];
if (c[13]) {
  x q[5];
}
if (c[12]) {
  z q[5];
}
swap q[5], q[3];
reset q[6];
reset q[8];
reset q[5];
reset q[5];
reset q[2];
reset q[0];
h q[5];
cx q[5], q[2];
cx q[3], q[5];
h q[3];
c[14] = measure q[3];
c[15] = measure q[5];
if (c[15]) {
  x q[2];
}
if (c[14]) {
  z q[2];
}
swap q[2], q[0];
reset q[3];
reset q[5];
reset q[2];
