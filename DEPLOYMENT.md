# Deployment

## Event Grid subscription for the blob trigger (Flex Consumption)

On the Flex Consumption plan, blob triggers must use Event Grid: polling is not supported. `process_incoming_blob` already uses Event Grid in Azure (leave `BLOB_TRIGGER_SOURCE` unset). Azure will not run it until an Event Grid subscription on the storage account sends `BlobCreated` events for the `incoming` container to the function's webhook.

### Before you start

- The code is deployed to the Function App and the app has started at least once. The `blobs_extension` key and the webhook endpoint exist only after that.
- `STORAGE_CONNECTION_STRING` is set and points at the storage account that has the `incoming` container. That account must be a **StorageV2 (general purpose v2)** account.
- The `Microsoft.EventGrid` resource provider is registered: **Subscriptions** > your subscription > **Settings** > **Resource providers** > search `Microsoft.EventGrid` > **Register** (skip if it already shows *Registered*).

### 1. Get the `blobs_extension` key

Portal: **Function App** > **Functions** > **App keys** > **System keys** > `blobs_extension` > click the value to show it, then copy it.

Or with the Azure CLI:

```bash
az functionapp keys list -g <RESOURCE_GROUP> -n <FUNCTION_APP_NAME> --query systemKeys.blobs_extension -o tsv
```

If `blobs_extension` is missing, the app has not loaded the blob trigger yet. Check that the deployment succeeded, open **Functions** to confirm `process_incoming_blob` is listed, then restart the app and check again.

### 2. Build the webhook URL

```
https://<FUNCTION_APP_HOST>/runtime/webhooks/blobs?functionName=Host.Functions.process_incoming_blob&code=<BLOBS_EXTENSION_KEY>
```

- `<FUNCTION_APP_HOST>`: the **Default domain** on the Function App's **Overview** page. For a classic hostname this is `<FUNCTION_APP_NAME>.azurewebsites.net`. If the app was created with a unique default hostname, it looks like `<FUNCTION_APP_NAME>-<hash>.<region>-01.azurewebsites.net`. Always copy the value shown on **Overview**.
- `process_incoming_blob` is the function name from `function_app.py`, with the `Host.Functions.` prefix.
- `<BLOBS_EXTENSION_KEY>`: the key from step 1.

Example for an app named `hr-onboarding-func`:

```
https://hr-onboarding-func.azurewebsites.net/runtime/webhooks/blobs?functionName=Host.Functions.process_incoming_blob&code=<BLOBS_EXTENSION_KEY>
```

### 3. Create the event subscription

1. Portal: open the **storage account** (the one in `STORAGE_CONNECTION_STRING`) > **Events** > **+ Event Subscription**.
2. **Basic** tab:
   - **Name**: `incoming-blob-created`
   - **Event Schema**: `Event Grid Schema`
   - **System Topic Name**: any name, e.g. `<STORAGE_ACCOUNT_NAME>-topic`. This box appears only if the storage account has no system topic yet.
   - **Filter to Event Types**: select **Blob Created** only (clear *Blob Deleted*)
   - **Endpoint Type**: `Web Hook`
   - **Endpoint**: **Configure an endpoint** > paste the URL from step 2 > **Confirm Selection**
3. **Filters** tab:
   - Tick **Enable subject filtering**
   - **Subject Begins With**: `/blobServices/default/containers/incoming/`

   With this filter, only uploads to `incoming` trigger the function. Blobs it moves into `passports`, `driving-licences` and `employee-documents` do not.
4. Click **Create**. Event Grid then sends a validation request to the webhook, and the blob extension answers it automatically. If creation fails at this step, check the URL (host, function name and key) and confirm the app is running.

### 4. Check that it works

1. Upload a file to the `incoming` container. For example, use **Storage browser**, or run `python upload_samples.py` with `STORAGE_CONNECTION_STRING` set to the Azure account.
2. Open **Function App** > **Log stream** (or **Functions** > `process_incoming_blob` > **Invocations**). You should see an invocation within a few seconds.
3. The file should move out of `incoming` into its routed container, unless it was marked `NeedsReview`. A row should appear in `ClassificationResults`.
4. On the storage account, **Events** > the subscription > **Metrics** shows delivered and failed events if nothing arrives.
