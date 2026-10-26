/**
 * EN:
 * Detect the client's real public IPv4 by
 * making an IPv4-only request to ipify.
 *
 * JSONP is used so the browser does not
 * depend on cross-origin fetch permissions.
 *
 * VI:
 * Phát hiện public IPv4 thật của client bằng
 * cách gửi request IPv4-only tới ipify.
 *
 * Sử dụng JSONP để browser không phụ thuộc
 * vào quyền cross-origin của fetch.
 */
export function getPublicIPv4() {
  return new Promise(
    (resolve, reject) => {
      const callbackName =
        `__publicIPv4Callback_${Date.now()}_${Math.random()
          .toString(36)
          .slice(2)}`;

      const script =
        document.createElement(
          "script"
        );

      const cleanup = () => {
        delete window[
          callbackName
        ];

        script.remove();
      };

      window[callbackName] = (
        data
      ) => {
        cleanup();

        if (
          !data ||
          typeof data.ip !== "string"
        ) {
          reject(
            new Error(
              "IPv4 service returned an invalid response."
            )
          );

          return;
        }

        resolve(data.ip);
      };

      script.onerror = () => {
        cleanup();

        reject(
          new Error(
            "Unable to detect public IPv4."
          )
        );
      };

      script.src =
        "https://api.ipify.org" +
        "?format=jsonp" +
        `&callback=${callbackName}`;

      document.head.appendChild(
        script
      );
    }
  );
}


/**
 * EN:
 * Send the IPv4 detected by the browser to
 * the Chatbot backend for validation.
 *
 * VI:
 * Gửi IPv4 mà browser phát hiện về Chatbot
 * backend để kiểm tra tính hợp lệ.
 */
export async function confirmPublicIPv4(
  publicIPv4
) {
  const response = await fetch(
    "/talk-sketch/chatbot-api/client-ip/confirm",
    {
      method: "POST",

      headers: {
        "Content-Type":
          "application/json",
      },

      body: JSON.stringify({
        public_ipv4:
          publicIPv4,
      }),
    }
  );

  const text =
    await response.text();

  if (!response.ok) {
    throw new Error(
      `IPv4 confirmation failed: ${text}`
    );
  }

  return JSON.parse(text);
}


/**
 * EN:
 * Detect the client's public IPv4 and then
 * validate it with the Chatbot backend.
 *
 * VI:
 * Phát hiện public IPv4 của client rồi
 * kiểm tra nó với Chatbot backend.
 */
export async function getConfirmedPublicIPv4() {
  const publicIPv4 =
    await getPublicIPv4();

  console.log(
    "[Chatbot] detected public IPv4:",
    publicIPv4
  );

  return await confirmPublicIPv4(
    publicIPv4
  );
}
