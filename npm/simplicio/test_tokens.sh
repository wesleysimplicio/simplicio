#!/bin/bash
# test npm tokens
echo "--- Test 1 ---"
curl -s -w "\nHTTP_CODE:%{http_code}" -H "Authorization: Bearer *** https://registry.npmjs.org/-/whoami
echo ""
echo "--- Test 2 ---"
curl -s -w "\nHTTP_CODE:%{http_code}" -H "Authorization: Bearer *** https://registry.npmjs.org/-/whoami
echo ""
