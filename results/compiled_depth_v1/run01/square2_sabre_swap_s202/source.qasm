OPENQASM 3.0;
include "stdgates.inc";
swap $2, $0;
swap $8, $2;
swap $11, $8;
cx $11, $9;
