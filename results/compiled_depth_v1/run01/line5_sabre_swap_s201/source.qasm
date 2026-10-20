OPENQASM 3.0;
include "stdgates.inc";
swap $2, $0;
swap $5, $2;
swap $8, $5;
swap $14, $12;
swap $11, $14;
cx $8, $11;
