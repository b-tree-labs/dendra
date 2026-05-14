// Copyright (c) 2026 B-Tree Labs
// SPDX-License-Identifier: LicenseRef-BSL-1.1
//
// One-time generation of the Ed25519 keypair used to sign Postrule
// license tokens. The PUBLIC key gets baked into the postrule Python
// package + sample docs (so offline verifiers can check signatures
// without us in the loop). The PRIVATE key gets installed as a wrangler
// secret on the api Worker:
//
//   STRIPE_KEY=… npx tsx scripts/generate-license-key.ts
//   wrangler secret put LICENSE_SIGNING_PRIVATE_KEY            # paste private hex
//   wrangler secret put LICENSE_SIGNING_PRIVATE_KEY --env=production
//
// Run separately for staging + production so a key compromise on one
// doesn't blow up the other.

// We intentionally use the Workers-style SubtleCrypto exposed by Node 20+;
// the same code runs in the api Worker and in this CLI.

const ENCODER = new TextEncoder();
void ENCODER; // mark as intentionally unused

async function main() {
  const kp = (await crypto.subtle.generateKey(
    { name: 'Ed25519' },
    true,
    ['sign', 'verify'],
  )) as CryptoKeyPair;

  const pkcs8 = new Uint8Array(await crypto.subtle.exportKey('pkcs8', kp.privateKey));
  const spki = new Uint8Array(await crypto.subtle.exportKey('spki', kp.publicKey));

  const privRaw = pkcs8.slice(pkcs8.length - 32);
  const pubRaw = spki.slice(spki.length - 32);

  const toHex = (bs: Uint8Array) =>
    [...bs].map((b) => b.toString(16).padStart(2, '0')).join('');

  console.log('=== Ed25519 keypair generated ===');
  console.log('');
  console.log('PUBLIC key (paste into Python package + docs):');
  console.log(`  ${toHex(pubRaw)}`);
  console.log('');
  console.log('PRIVATE key (paste at the wrangler secret prompt):');
  console.log(`  ${toHex(privRaw)}`);
  console.log('');
  console.log('Next step (from cloud/api/):');
  console.log('  wrangler secret put LICENSE_SIGNING_PRIVATE_KEY');
  console.log('  wrangler secret put LICENSE_SIGNING_PRIVATE_KEY --env=production');
  console.log('');
  console.log('After setting both, the public key is what verifiers use.');
  console.log('Embed it in src/postrule/license.py LICENSE_PUBLIC_KEY_HEX.');
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
