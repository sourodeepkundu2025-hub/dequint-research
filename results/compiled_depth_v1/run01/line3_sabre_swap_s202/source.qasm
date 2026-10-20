OPENQASM 3.0;
include "stdgates.inc";
swap $2, $0;
swap $5, $2;
swap $8, $5;
cx $8, $6;
