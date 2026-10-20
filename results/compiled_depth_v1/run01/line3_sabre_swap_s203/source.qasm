OPENQASM 3.0;
include "stdgates.inc";
swap $2, $0;
swap $8, $6;
swap $5, $8;
cx $2, $5;
